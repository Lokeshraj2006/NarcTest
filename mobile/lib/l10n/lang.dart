import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:provider/provider.dart';

/// App language: English (default) or Tamil. The choice is saved on the phone.
class LangProvider extends ChangeNotifier {
  static const _key = 'app_language';
  static const _storage = FlutterSecureStorage();

  String _code = 'en';
  bool get isTamil => _code == 'ta';

  Future<void> load() async {
    try {
      _code = (await _storage.read(key: _key)) ?? 'en';
    } catch (_) {
      _code = 'en';
    }
  }

  Future<void> toggle() async {
    _code = isTamil ? 'en' : 'ta';
    notifyListeners();
    try {
      await _storage.write(key: _key, value: _code);
    } catch (_) {}
  }
}

/// Text in the chosen language (use inside build). The English text is the key;
/// anything without a Tamil entry is shown in English.
String tr(BuildContext context, String en, [List<Object?> args = const []]) =>
    _pick(Provider.of<LangProvider>(context).isTamil, en, args);

/// Same as [tr] but safe inside button callbacks (does not listen for changes).
String trNow(BuildContext context, String en, [List<Object?> args = const []]) =>
    _pick(Provider.of<LangProvider>(context, listen: false).isTamil, en, args);

String _pick(bool tamil, String en, List<Object?> args) {
  var s = tamil ? (_ta[en] ?? en) : en;
  for (var i = 0; i < args.length; i++) {
    s = s.replaceAll('{$i}', '${args[i]}');
  }
  return s;
}

/// Small button that switches English <-> Tamil.
class LangButton extends StatelessWidget {
  final Color? color;
  const LangButton({super.key, this.color});

  @override
  Widget build(BuildContext context) {
    final lang = Provider.of<LangProvider>(context);
    return TextButton(
      onPressed: lang.toggle,
      style: TextButton.styleFrom(foregroundColor: color),
      child: Text(lang.isTamil ? 'English' : 'தமிழ்',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
    );
  }
}

const Map<String, String> _ta = {
  // Login
  'Digital Companion for Field Drug Testing': 'களத்தில் போதைப்பொருள் சோதனைக்கான டிஜிட்டல் உதவியாளர்',
  'Username': 'பயனர் பெயர்',
  'Password': 'கடவுச்சொல்',
  'Please fill this': 'இதை நிரப்பவும்',
  'Log in': 'உள்நுழை',
  'Demo login (tap to fill):': 'டெமோ உள்நுழைவு (தட்டினால் நிரம்பும்):',
  'Backend settings': 'சர்வர் அமைப்புகள்',
  // Home
  'Hello!': 'வணக்கம்!',
  'Hello, {0}!': 'வணக்கம், {0}!',
  'Test a drug kit, get a sealed record.': 'கிட்டை சோதித்து, சீல் செய்த பதிவைப் பெறுங்கள்.',
  'New Test': 'புதிய சோதனை',
  'Pick the kit and take a photo': 'கிட்டைத் தேர்ந்தெடுத்து புகைப்படம் எடுக்கவும்',
  'My Tests': 'என் சோதனைகள்',
  'See the tests you already did': 'நீங்கள் செய்த சோதனைகளைப் பார்க்கவும்',
  'Settings': 'அமைப்புகள்',
  'Change the server address': 'சர்வர் முகவரியை மாற்றவும்',
  'Logout': 'வெளியேறு',
  'Sign out of this phone': 'இந்த போனிலிருந்து வெளியேறவும்',
  // Kit picker
  'Pick your test kit': 'சோதனை கிட்டைத் தேர்ந்தெடுக்கவும்',
  'No test kits found on the server.': 'சர்வரில் சோதனை கிட் எதுவும் இல்லை.',
  'Try again': 'மீண்டும் முயற்சி செய்',
  'Wait {0} seconds before reading': 'படிக்கும் முன் {0} வினாடி காத்திருக்கவும்',
  'Use this kit': 'இந்த கிட்டைப் பயன்படுத்து',
  // Camera
  'Camera is not working. Please allow camera permission and open this screen again.':
      'கேமரா வேலை செய்யவில்லை. கேமரா அனுமதி கொடுத்து இந்த திரையை மீண்டும் திறக்கவும்.',
  'Could not take the photo. Please try again.': 'புகைப்படம் எடுக்க முடியவில்லை. மீண்டும் முயற்சி செய்யவும்.',
  'Keep the colour card inside the box': 'வண்ண அட்டையை பெட்டிக்குள் வைக்கவும்',
  'Start timer ({0}s)': 'டைமர் தொடங்கு ({0} வி)',
  'Stop timer': 'டைமர் நிறுத்து',
  'Capture now': 'இப்போது எடு',
  'Photo looks blurry or dark': 'புகைப்படம் மங்கலாக அல்லது இருட்டாக உள்ளது',
  'Hold the phone steady, keep the card in good light and take it again.':
      'போனை அசையாமல் பிடித்து, அட்டையை நல்ல வெளிச்சத்தில் வைத்து மீண்டும் எடுக்கவும்.',
  'Send anyway': 'இருந்தாலும் அனுப்பு',
  'Take again': 'மீண்டும் எடு',
  'Take photo again': 'மீண்டும் புகைப்படம் எடு',
  // Saving
  'Saving test': 'சோதனை சேமிக்கப்படுகிறது',
  'Getting your location...': 'உங்கள் இருப்பிடம் எடுக்கப்படுகிறது...',
  'Sealing your test record...': 'சோதனை பதிவு சீல் செய்யப்படுகிறது...',
  'Please wait, do not close the app.': 'காத்திருக்கவும், ஆப்பை மூட வேண்டாம்.',
  'Try sending again': 'மீண்டும் அனுப்பு',
  'Go back': 'பின் செல்',
  // Result
  'Test #{0}': 'சோதனை #{0}',
  'POSITIVE': 'பாசிட்டிவ் (POSITIVE)',
  'NEGATIVE': 'நெகட்டிவ் (NEGATIVE)',
  'NOT SURE (INCONCLUSIVE)': 'உறுதியாக சொல்ல முடியவில்லை',
  'NOT SURE': 'உறுதியில்லை',
  '{0}% sure': '{0}% உறுதி',
  'Colour seen vs kit colours': 'தெரிந்த நிறம் மற்றும் கிட் நிறங்கள்',
  'Your test': 'உங்கள் சோதனை',
  'Record details': 'பதிவு விவரங்கள்',
  'Test ID': 'சோதனை எண்',
  'Kit': 'கிட்',
  'Time': 'நேரம்',
  'Officer': 'அதிகாரி',
  'Photo hash': 'புகைப்பட ஹாஷ்',
  'Record hash': 'பதிவு ஹாஷ்',
  'Sealed & signed': 'சீல் செய்து கையொப்பமிடப்பட்டது',
  '(photo hash did not match!)': '(புகைப்பட ஹாஷ் பொருந்தவில்லை!)',
  'Open verify page': 'சரிபார்ப்பு பக்கத்தைத் திற',
  'Not available': 'கிடைக்கவில்லை',
  'internet time (NTP)': 'இணைய நேரம் (NTP)',
  'internet time (HTTPS)': 'இணைய நேரம் (HTTPS)',
  'server clock': 'சர்வர் கடிகாரம்',
  ' - FAKE GPS!': ' - போலி GPS!',
  'Could not open {0}': '{0} திறக்க முடியவில்லை',
  'Presumptive field result — not a substitute for laboratory confirmatory testing.':
      'இது களத்தில் செய்த முதற்கட்ட முடிவு மட்டுமே. ஆய்வக உறுதிச் சோதனைக்கு மாற்று அல்ல.',
  // My tests
  'No tests yet. Tap "New Test" on Home to start.': 'இன்னும் சோதனை இல்லை. தொடங்க முகப்பில் "புதிய சோதனை" தட்டவும்.',
  'Test #{0} · {1}': 'சோதனை #{0} · {1}',
  // Reasons sent by the server (colour_engine.REASONS)
  'Could not open the photo — please retake': 'புகைப்படத்தைத் திறக்க முடியவில்லை - மீண்டும் எடுக்கவும்',
  'Colour card not found — keep all 4 corner squares in the photo':
      'வண்ண அட்டை தெரியவில்லை - 4 மூலை சதுரங்களும் புகைப்படத்தில் இருக்க வேண்டும்',
  'Photo is blurry — hold the phone steady and retake': 'புகைப்படம் மங்கலாக உள்ளது - போனை அசையாமல் பிடித்து மீண்டும் எடுக்கவும்',
  'Shine/glare on the card — tilt the phone a little and retake':
      'அட்டையில் வெளிச்சம் பிரதிபலிக்கிறது - போனை சிறிது சாய்த்து மீண்டும் எடுக்கவும்',
  'Colour card could not be read properly — retake in even light':
      'வண்ண அட்டையை சரியாக படிக்க முடியவில்லை - சீரான வெளிச்சத்தில் மீண்டும் எடுக்கவும்',
  'Colour does not match any result of this kit': 'இந்த நிறம் இந்த கிட்டின் எந்த முடிவோடும் பொருந்தவில்லை',
  'Colour is in between two results — not sure': 'நிறம் இரண்டு முடிவுகளுக்கு இடையில் உள்ளது - உறுதியில்லை',
  // Kit colour names (kit_service.DEMO_KITS)
  'Opium-type drug (purple)': 'ஓபியம் வகை போதைப்பொருள் (ஊதா)',
  'Amphetamine-type drug (orange)': 'ஆம்பெட்டமைன் வகை போதைப்பொருள் (ஆரஞ்சு)',
  'No reaction (no colour change)': 'எதிர்வினை இல்லை (நிற மாற்றம் இல்லை)',
  'Starch found (blue-black)': 'ஸ்டார்ச் உள்ளது (நீல-கருப்பு)',
  'No starch (amber)': 'ஸ்டார்ச் இல்லை (அம்பர்)',
  // Errors (ApiService.friendlyError)
  'Your login has expired. Please log in again.': 'உங்கள் உள்நுழைவு காலாவதியானது. மீண்டும் உள்நுழையவும்.',
  'You are not allowed to do this.': 'இதைச் செய்ய உங்களுக்கு அனுமதி இல்லை.',
  'Cannot reach the server. Check Wi-Fi and the server address in Settings.':
      'சர்வரை அணுக முடியவில்லை. Wi-Fi மற்றும் அமைப்புகளில் உள்ள சர்வர் முகவரியை சரிபார்க்கவும்.',
};
