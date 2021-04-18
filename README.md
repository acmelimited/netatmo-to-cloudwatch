# Netatmo to AWS CloudWatch
This is an inital Python application which is intended for an AWS Lambda function to pull weather station information from Netatmo and put it in CloudWatch (EventBridge) as a custom metric.

In my home, I have a weather station by Netatmo (https://www.netatmo.com/en-gb/weather) with various sensors around the house and in the garden. The have a various apps available for smart phones but I just wanted to also send this data to CloudWatch (EventBridge as it is now know) whilst as the same time nearing Python. So this is my first Python app which works in its current state but needs some further refactoring to clean it up.

For more information regarding the API from Netatmo please visit the following links:
https://dev.netatmo.com/apidocumentation
https://dev.netatmo.com/apidocumentation/weather

v0.1 - Initial release

TODO: In the coming days/weeks; create a CI/CD pipeline including some unit tests, add pylint and deploy using terraform. 
