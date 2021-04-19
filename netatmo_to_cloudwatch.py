"""Import the netatmo library"""
import pyatmo
import boto3

def lambda_handler(event, context):
    """This is the main entry point into the program for the Lambda function.
    This python script will extract the weather station data for your Netatmo
    and send it to CloudWatch/EventBridge as a custom metric.
    Please refer to https://dev.netatmo.com/guideline for more information.
    """
    data = fetch_weather_data()
    send_data_to_cloudwatch(data)


def fetch_weather_data():
    """This method will fetch the weather data from Netatmo"""

    ssm = boto3.client('ssm')

    # Need to get the secrets for use with the Netatmo API which are held in AWS Systems Manager.
    # You will need a client id and client secret from Netatmo which can be obtained when you
    # register your app with them https://dev.netatmo.com/apps/createanapp#form
    secrets = ssm.get_parameters(
        Names=['Netatmo_Client_Id',
               'Netatmo_Username',
               'Netatmo_Client_Secret',
               'Netatmo_Password'],
        WithDecryption=True)

    # Parse the secrets returned from AWS Systems Manager
    parsed_secrets = parse_secrets_parameters(secrets)

    # Now authorise against Netatmo
    authorization = pyatmo.ClientAuth(
        client_id = parsed_secrets['Netatmo_Client_Id'],
        client_secret = parsed_secrets['Netatmo_Client_Secret'],
        username = parsed_secrets['Netatmo_Username'],
        password = parsed_secrets['Netatmo_Password'],
    )

    # Request the weather station data from Netatmo
    # The response contains the latest readings from the base station,
    # Outside modules and all modules indoors.
    metric_data = []
    weather_data = pyatmo.WeatherStationData(authorization)

    # It is possible to own more than one base station
    for station_key in weather_data.stations:
        station = weather_data.stations[station_key]

        station_name = get_data("module_name", station)

        # The time is returned in epoch format
        station_time = get_dashboard_data("time_utc", station)

        # For each metric associated with the station that we want to send to CloudWatch
        # we append each metric to the list
        station_temp = get_dashboard_data("Temperature", station)
        metric_data.append(
            create_metric_data("Temperature", station_name, station_temp, station_time))

        station_co2 = get_dashboard_data("CO2", station)
        metric_data.append(
            create_metric_data("CO2", station_name, station_co2, station_time))

        station_humidity = get_dashboard_data("Humidity", station)
        metric_data.append(
            create_metric_data("Humidity", station_name, station_humidity, station_time))

        station_noise = get_dashboard_data("Noise", station)
        metric_data.append(create_metric_data("Noise", station_name, station_noise, station_time))

        station_pressure = get_dashboard_data("Pressure", station)
        metric_data.append(
            create_metric_data("Air_Pressure", station_name, station_pressure, station_time))

        # Now iterate over the modules; these are the indoors and outdoors modules
        for module in station["modules"]:
            # Battery is dead, no wifi signal or there is a problem with the module.
            # In this case the module is not reporting any data so there is nothing to collect.
            if not module["reachable"] :
                continue

            module_name = get_data("module_name", module)
            module_time = get_dashboard_data("time_utc", module)

            # The rf_status is the signal strength.
            # Please refer to https://dev.netatmo.com/apidocumentation/weather
            # for an explaination of the values.
            module_signal = get_data("rf_status", module)
            metric_data.append(
                create_metric_data("Signal_Strength", module_name, module_signal, module_time))

            # The battery_vp is a number to indicate the health of the battery.
            # Depending on the module, the values will mean a different status.
            # Please refer to https://dev.netatmo.com/apidocumentation/weather
            # for an explaination of the values.
            module_battery = get_data("battery_vp", module)
            metric_data.append(
                create_metric_data("Battery_Status", module_name, module_battery, module_time))

            # This is for indoor and outdoor temperature modules
            if "Temperature" in module["data_type"]:
                module_temperature = get_dashboard_data("Temperature", module)
                metric_data.append(
                    create_metric_data("Temperature", module_name, module_temperature, module_time))

                module_humidity = get_dashboard_data("Humidity", module)
                metric_data.append(
                    create_metric_data("Humidity", module_name, module_humidity, module_time))

            # Only the indoor modules have CO2 sensor
            if "CO2" in module["data_type"]:
                module_co2 = get_dashboard_data("CO2", module)
                metric_data.append(create_metric_data("CO2", module_name, module_co2, module_time))

            # Rain gauage
            if "Rain" in module["data_type"]:
                module_rain = get_dashboard_data("Rain", module)
                metric_data.append(
                    create_metric_data("Rain", module_name, module_rain, module_time))

                module_rain_1hour = get_dashboard_data("sum_rain_1", module)
                metric_data.append(
                    create_metric_data("Rain_1_hour", module_name, module_rain_1hour, module_time))

                module_rain_24hour = get_dashboard_data("sum_rain_24", module)
                metric_data.append(
                    create_metric_data(
                        "Rain_24_hours",
                        module_name,
                        module_rain_24hour,
                        module_time))

            # TODO: Wind gauge. I need to get some new batteries for mine....
    return metric_data

def get_dashboard_data(item_name, source):
    """Helper method to parse the dashboard data from whic contains the weather information
    for either a station or module
    """

    if "dashboard_data" in source:
        return source["dashboard_data"].get(item_name)
    return None


def get_data(item_name, source):
    """Helper method to get the value out of the dictionary for particular key
    """
    return source.get(item_name)

def create_metric_data(metric_name, dimension_value, metric_value, metric_timestamp):
    """Method to create the structure of a custom metric in the format expected by CloudWatch
    """
    return {
                "MetricName": metric_name,
                "Dimensions": [
                {
                    "Name": "ModuleName",
                    "Value": dimension_value
                },
                ],
                "Unit": "None",
                "Value": metric_value,
                "Timestamp": metric_timestamp,
            }

def send_data_to_cloudwatch(event_data):
    """Method to send the collected data to CloudWatch
    """
    item_count = len(event_data)
    current_position = 0

    # Loop over all the event data that we have.
    # We can only send in 20 metrics with each call.
    while current_position < item_count:
        # TODO: refactor out the 20
        end_position = current_position + 20 - 1

        # Check to ensure that the range is not outside of the list length
        if end_position >= item_count:
            end_position = item_count - 1

        # Get a range of events to end
        data = event_data[current_position:end_position]

        # Send to CloudWatch
        cloudwatch = boto3.client('cloudwatch')
        response = cloudwatch.put_metric_data(
            MetricData = data,
            Namespace = 'Deansystems/Netatmo'
        )

        # Move the postion on to the next 20 events
        current_position += 20

        print(response)

def parse_secrets_parameters(secrets):
    """Method to parse the object returned from Systems Manager
    and to collected the secret parameters that were requested.
    """
    parsed_secrets = {}
    for parameter in secrets['Parameters']:
        name = parameter.get('Name')
        value = parameter.get('Value')
        parsed_secrets[name] = value

    return parsed_secrets
