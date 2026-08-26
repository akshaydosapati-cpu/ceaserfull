import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import os

class WeatherAssistant:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Weather Assistant with OpenWeatherMap API key"""
        self.api_key = api_key or os.getenv('OPENWEATHER_API_KEY') or os.getenv('WEATHER_API_KEY')
        self.base_url = (os.getenv('WEATHER_API_BASE_URL') or "https://api.openweathermap.org/data/2.5").rstrip("/")
        
    def get_current_weather(self, city: str, units: str = "metric") -> Dict:
        """Get current weather for a city"""
        url = f"{self.base_url}/weather"
        params = {
            'q': city,
            'appid': self.api_key,
            'units': units
        }
        
        try:
            if not self.api_key:
                return {'success': False, 'error': "Weather API key is not configured"}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('cod') == 200:
                return {
                    'success': True,
                    'city': data['name'],
                    'country': data['sys']['country'],
                    'temperature': data['main']['temp'],
                    'feels_like': data['main']['feels_like'],
                    'humidity': data['main']['humidity'],
                    'pressure': data['main']['pressure'],
                    'description': data['weather'][0]['description'],
                    'icon': data['weather'][0]['icon'],
                    'wind_speed': data['wind']['speed'],
                    'wind_direction': data['wind'].get('deg', 0),
                    'visibility': data.get('visibility', 0),
                    'clouds': data['clouds']['all'],
                    'sunrise': datetime.fromtimestamp(data['sys']['sunrise']),
                    'sunset': datetime.fromtimestamp(data['sys']['sunset']),
                    'timestamp': datetime.fromtimestamp(data['dt'])
                }
            else:
                return {'success': False, 'error': f"Weather API error: {data.get('message', 'Unknown error')}"}
                
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f"Network error: {str(e)}"}
        except Exception as e:
            return {'success': False, 'error': f"Unexpected error: {str(e)}"}
    
    def get_forecast(self, city: str, days: int = 5, units: str = "metric") -> Dict:
        """Get weather forecast for a city"""
        url = f"{self.base_url}/forecast"
        params = {
            'q': city,
            'appid': self.api_key,
            'units': units,
            'cnt': days * 8  # 8 forecasts per day (every 3 hours)
        }
        
        try:
            if not self.api_key:
                return {'success': False, 'error': "Weather API key is not configured"}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('cod') == '200':
                forecasts = []
                for item in data['list']:
                    forecast = {
                        'datetime': datetime.fromtimestamp(item['dt']),
                        'temperature': item['main']['temp'],
                        'feels_like': item['main']['feels_like'],
                        'humidity': item['main']['humidity'],
                        'description': item['weather'][0]['description'],
                        'icon': item['weather'][0]['icon'],
                        'wind_speed': item['wind']['speed'],
                        'wind_direction': item['wind'].get('deg', 0),
                        'clouds': item['clouds']['all'],
                        'pop': item.get('pop', 0)  # Probability of precipitation
                    }
                    forecasts.append(forecast)
                
                return {
                    'success': True,
                    'city': data['city']['name'],
                    'country': data['city']['country'],
                    'forecasts': forecasts
                }
            else:
                return {'success': False, 'error': f"Forecast API error: {data.get('message', 'Unknown error')}"}
                
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f"Network error: {str(e)}"}
        except Exception as e:
            return {'success': False, 'error': f"Unexpected error: {str(e)}"}
    
    def get_air_quality(self, city: str) -> Dict:
        """Get air quality data for a city"""
        # First get coordinates
        coords = self._get_coordinates(city)
        if not coords['success']:
            return coords
            
        url = f"{self.base_url}/air_pollution"
        params = {
            'lat': coords['lat'],
            'lon': coords['lon'],
            'appid': self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('cod') == 200:
                aqi_data = data['list'][0]
                return {
                    'success': True,
                    'city': city,
                    'aqi': aqi_data['main']['aqi'],  # Air Quality Index (1-5)
                    'components': aqi_data['components'],
                    'timestamp': datetime.fromtimestamp(aqi_data['dt'])
                }
            else:
                return {'success': False, 'error': f"Air quality API error: {data.get('message', 'Unknown error')}"}
                
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f"Network error: {str(e)}"}
        except Exception as e:
            return {'success': False, 'error': f"Unexpected error: {str(e)}"}
    
    def get_weather_alerts(self, city: str) -> Dict:
        """Get weather alerts for a city"""
        coords = self._get_coordinates(city)
        if not coords['success']:
            return coords
            
        url = f"{self.base_url}/onecall"
        params = {
            'lat': coords['lat'],
            'lon': coords['lon'],
            'appid': self.api_key,
            'exclude': 'current,minutely,hourly,daily',
            'units': 'metric'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'alerts' in data:
                alerts = []
                for alert in data['alerts']:
                    alert_info = {
                        'sender': alert['sender_name'],
                        'event': alert['event'],
                        'start': datetime.fromtimestamp(alert['start']),
                        'end': datetime.fromtimestamp(alert['end']),
                        'description': alert['description'],
                        'tags': alert.get('tags', [])
                    }
                    alerts.append(alert_info)
                
                return {
                    'success': True,
                    'city': city,
                    'alerts': alerts
                }
            else:
                return {
                    'success': True,
                    'city': city,
                    'alerts': [],
                    'message': 'No weather alerts for this location'
                }
                
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f"Network error: {str(e)}"}
        except Exception as e:
            return {'success': False, 'error': f"Unexpected error: {str(e)}"}
    
    def get_uv_index(self, city: str) -> Dict:
        """Get UV index for a city"""
        coords = self._get_coordinates(city)
        if not coords['success']:
            return coords
            
        url = f"{self.base_url}/uvi"
        params = {
            'lat': coords['lat'],
            'lon': coords['lon'],
            'appid': self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, dict) and 'value' in data:
                return {
                    'success': True,
                    'city': city,
                    'uv_index': data['value'],
                    'timestamp': datetime.fromtimestamp(data.get('dt', datetime.now().timestamp()))
                }
            elif isinstance(data, list) and len(data) > 0:
                return {
                    'success': True,
                    'city': city,
                    'uv_index': data[0].get('value', 0),
                    'timestamp': datetime.fromtimestamp(data[0].get('dt', datetime.now().timestamp()))
                }
            else:
                return {'success': False, 'error': f"Unexpected UV index response format: {data}"}
                
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f"Network error: {str(e)}"}
        except Exception as e:
            return {'success': False, 'error': f"Unexpected error: {str(e)}"}
    
    def _get_coordinates(self, city: str) -> Dict:
        """Get coordinates for a city"""
        url = f"{self.base_url}/weather"
        params = {
            'q': city,
            'appid': self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('cod') == 200:
                return {
                    'success': True,
                    'lat': data['coord']['lat'],
                    'lon': data['coord']['lon']
                }
            else:
                return {'success': False, 'error': f"City not found: {city}"}
                
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f"Network error: {str(e)}"}
        except Exception as e:
            return {'success': False, 'error': f"Unexpected error: {str(e)}"}
    
    def format_weather_report(self, weather_data: Dict) -> str:
        """Format weather data into a readable report"""
        if not weather_data['success']:
            return f"Sorry, I couldn't get the weather: {weather_data['error']}"
        
        weather = weather_data
        temp = weather['temperature']
        feels_like = weather['feels_like']
        description = weather['description'].title()
        humidity = weather['humidity']
        wind_speed = weather['wind_speed']
        
        report = f"Current weather in {weather['city']}, {weather['country']}: "
        report += f"{description} with a temperature of {temp}°C. "
        report += f"It feels like {feels_like}°C. "
        report += f"Humidity is {humidity}% and wind speed is {wind_speed} m/s."
        
        return report
    
    def format_forecast_report(self, forecast_data: Dict) -> str:
        """Format forecast data into a readable report"""
        if not forecast_data['success']:
            return f"Sorry, I couldn't get the forecast: {forecast_data['error']}"
        
        city = forecast_data['city']
        forecasts = forecast_data['forecasts']
        
        # Group by day
        daily_forecasts = {}
        for forecast in forecasts:
            date = forecast['datetime'].date()
            if date not in daily_forecasts:
                daily_forecasts[date] = []
            daily_forecasts[date].append(forecast)
        
        report = f"Weather forecast for {city}:\n"
        
        for date, day_forecasts in list(daily_forecasts.items())[:5]:  # Next 5 days
            # Calculate daily averages
            temps = [f['temperature'] for f in day_forecasts]
            avg_temp = sum(temps) / len(temps)
            max_temp = max(temps)
            min_temp = min(temps)
            
            # Get most common description
            descriptions = [f['description'] for f in day_forecasts]
            most_common_desc = max(set(descriptions), key=descriptions.count)
            
            day_name = date.strftime('%A')
            report += f"{day_name}: {most_common_desc.title()}, "
            report += f"High {max_temp:.1f}°C, Low {min_temp:.1f}°C\n"
        
        return report
    
    def format_air_quality_report(self, aqi_data: Dict) -> str:
        """Format air quality data into a readable report"""
        if not aqi_data['success']:
            return f"Sorry, I couldn't get air quality data: {aqi_data['error']}"
        
        city = aqi_data['city']
        aqi = aqi_data['aqi']
        components = aqi_data['components']
        
        # AQI levels
        aqi_levels = {
            1: "Good",
            2: "Fair", 
            3: "Moderate",
            4: "Poor",
            5: "Very Poor"
        }
        
        level = aqi_levels.get(aqi, "Unknown")
        
        report = f"Air quality in {city}: {level} (AQI: {aqi}). "
        report += f"PM2.5: {components.get('pm2_5', 'N/A')} μg/m³, "
        report += f"PM10: {components.get('pm10', 'N/A')} μg/m³, "
        report += f"Ozone: {components.get('o3', 'N/A')} μg/m³."
        
        return report
    
    def format_weather_alerts_report(self, alerts_data: Dict) -> str:
        """Format weather alerts into a readable report"""
        if not alerts_data['success']:
            return f"Sorry, I couldn't get weather alerts: {alerts_data['error']}"
        
        city = alerts_data['city']
        alerts = alerts_data['alerts']
        
        if not alerts:
            return f"No weather alerts for {city} at this time."
        
        report = f"Weather alerts for {city}:\n"
        
        for alert in alerts:
            event = alert['event']
            start = alert['start'].strftime('%B %d at %I:%M %p')
            end = alert['end'].strftime('%B %d at %I:%M %p')
            description = alert['description'][:200] + "..." if len(alert['description']) > 200 else alert['description']
            
            report += f"• {event} from {start} to {end}\n"
            report += f"  {description}\n\n"
        
        return report
    
    def get_comprehensive_weather(self, city: str) -> str:
        """Get comprehensive weather information including current, forecast, air quality, and alerts"""
        current = self.get_current_weather(city)
        forecast = self.get_forecast(city, days=3)
        air_quality = self.get_air_quality(city)
        alerts = self.get_weather_alerts(city)
        
        report = self.format_weather_report(current) + "\n\n"
        report += self.format_forecast_report(forecast) + "\n"
        report += self.format_air_quality_report(air_quality) + "\n\n"
        report += self.format_weather_alerts_report(alerts)
        
        return report
    
    def get_weather_summary(self, city: str) -> str:
        """Get a quick weather summary"""
        current = self.get_current_weather(city)
        if not current['success']:
            return f"Sorry, I couldn't get the weather for {city}: {current['error']}"
        
        temp = current['temperature']
        description = current['description'].title()
        humidity = current['humidity']
        
        summary = f"Quick weather for {city}: {description}, {temp}°C, {humidity}% humidity."
        return summary
    
    def get_rain_forecast(self, city: str) -> str:
        """Get rain forecast for the next few days"""
        forecast = self.get_forecast(city, days=5)
        if not forecast['success']:
            return f"Sorry, I couldn't get the rain forecast: {forecast['error']}"
        
        city_name = forecast['city']
        forecasts = forecast['forecasts']
        
        # Check for rain in next 5 days
        rain_days = []
        for forecast in forecasts:
            if forecast['pop'] > 0.3:  # More than 30% chance of rain
                date = forecast['datetime'].strftime('%A')
                time = forecast['datetime'].strftime('%I:%M %p')
                chance = int(forecast['pop'] * 100)
                rain_days.append(f"{date} at {time} ({chance}% chance)")
        
        if rain_days:
            report = f"Rain forecast for {city_name}: Rain expected on "
            report += ", ".join(rain_days[:3])  # Show first 3 rain periods
            if len(rain_days) > 3:
                report += f" and {len(rain_days) - 3} other times"
        else:
            report = f"No significant rain expected in {city_name} for the next 5 days."
        
        return report 
