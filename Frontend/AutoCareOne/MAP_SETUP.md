# OpenStreetMap Setup Instructions

## Overview
The app uses **OpenStreetMap** with `flutter_map` to show the user's current location. This is completely **FREE** and requires **NO API KEY**!

## Features
- ✅ Completely free - no API key needed
- ✅ Open source
- ✅ Real map tiles from OpenStreetMap
- ✅ Shows user's current location
- ✅ Professional appearance similar to Google Maps
- ✅ No usage limits

## Dependencies
The following packages are used:
- `flutter_map: ^7.0.2` - Map widget using OpenStreetMap tiles
- `latlong2: ^0.9.1` - Geographic coordinates handling
- `geolocator: ^10.1.0` - Get user's current location

## Permissions

### Android
Location permissions are already configured in `android/app/src/main/AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
```

### iOS
Location usage descriptions are configured in `ios/Runner/Info.plist`:
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>This app needs access to your location to show your vehicle's current position on the map.</string>
```

## Usage
The map automatically:
1. Requests location permission when first opened
2. Gets the user's current location
3. Displays the location on an OpenStreetMap tile
4. Shows a blue marker at the current location

## Troubleshooting

### Location not showing
- Make sure location permissions are granted
- Check if location services are enabled on your device
- For Android: Verify location permissions in AndroidManifest.xml
- For iOS: Verify location usage descriptions in Info.plist

### Map shows blank
- Check your internet connection (OpenStreetMap tiles require internet)
- Verify that `flutter_map` and `latlong2` packages are installed
- Run `flutter clean` and `flutter pub get`

### Build errors
- Run `flutter clean` and `flutter pub get`
- For iOS: Make sure you've run `pod install` in the `ios` directory
- Check that all dependencies are properly installed

## Advantages over Google Maps
- ✅ **No API key required** - works immediately
- ✅ **Completely free** - no usage limits
- ✅ **Open source** - community-driven
- ✅ **Privacy-friendly** - no tracking
- ✅ **No billing account needed**

## Note
OpenStreetMap tiles are provided by the OpenStreetMap Foundation. Please respect their [Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/) when using in production apps.

