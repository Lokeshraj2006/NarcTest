# FieldProof mobile app

The Flutter (Android) app for **consumers** and **inspectors**. Admins use the
web dashboard; the app shows them a redirect screen. Setup for the whole
project, including the server, is in the [main README](../README.md).

## What it does

| Role | What they can do |
| --- | --- |
| Consumer | Scan a label (camera or gallery), check the filled-in fields, add photos of other faces, see the result, see their own past scans |
| Inspector | Everything a consumer can, plus pending complaints (list and map), every scan with who took it, scan details, and filing a violation report |

A scan goes: **capture → Review Details → result**.

- Google ML Kit reads the text and barcode **on the phone**; there is no cloud
  OCR.
- `lib/services/field_extractor.dart` pairs each heading (NET QUANTITY, MRP,
  MFG. DATE…) with its value by position. It is built to survive real OCR
  mistakes, and each one it handles has a test on real OCR text in `test/`.
- On Review Details the user can fix any field. Every change is sent with the
  scan and recorded. **Scan another part** adds up to 3 photos of other faces
  (seal, lid, veg mark); the server checks them for the veg mark.
- The photo is fingerprinted (SHA-256) and sent with GPS and the phone's time,
  checked against internet (NTP) time.

## Build and install

```bash
flutter pub get
flutter build apk --debug --dart-define="LABELGUARD_API_BASE=http://localhost:8000"
adb install -r build/app/outputs/flutter-apk/app-debug.apk
adb reverse tcp:8000 tcp:8000
```

- `LABELGUARD_API_BASE` is the backend address baked into the build. It can
  be changed later in the app's **Settings**, with no rebuild. With nothing
  set, the app uses `http://10.0.2.2:8000`, which is the Android emulator's
  way to reach the laptop.
- `adb reverse` makes the phone's `localhost:8000` reach the laptop over USB.
  Run it again after the phone is unplugged or sleeps.
- Needs JDK 17 or 21 and Android NDK `28.2.13676358`. On Windows, create
  `C:\jtmp` first: `android/gradle.properties` points a JDK setting there,
  because a space in the Windows user name breaks Gradle.

`scripts/build_and_serve.py` builds the APK, serves it on your network and
prints a QR code for installing it on a phone without a cable.

## Code layout

```
lib/
  models/       API data shapes (scan result, inspection detail, reports…)
  providers/    app state (login, scans, scan log, complaints)
  services/     API client, OCR, barcode, GPS, NTP, hashing, field extractor, settings
  screens/
    auth/       login
    consumer/   home, scan capture, Review Details, result, my scans
    inspector/  home, pending complaints, map, scan log, scan detail, file report
    admin/      redirect to the dashboard
  utils/        verdict labels and colours, server time parsing, "printed elsewhere" hints
  widgets/      shared UI pieces
test/           unit and widget tests, with OCR text from real scans as fixtures
```

Server timestamps must be parsed with `parseServerTime`
(`lib/utils/server_time.dart`), not `DateTime.parse`. Otherwise times show
hours off.

## Tests

```bash
flutter analyze
flutter test
```
