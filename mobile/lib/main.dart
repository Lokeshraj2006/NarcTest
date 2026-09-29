import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'l10n/lang.dart';
import 'providers/auth_provider.dart';
import 'screens/splash_screen.dart';
import 'services/settings_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Load the saved server URL before the first request.
  await SettingsService.load();
  final lang = LangProvider();
  await lang.load();
  runApp(FieldProofApp(lang: lang));
}

class FieldProofApp extends StatelessWidget {
  final LangProvider lang;
  const FieldProofApp({super.key, required this.lang});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider.value(value: lang),
      ],
      child: MaterialApp(
        title: 'FieldProof',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          colorScheme: ColorScheme.fromSeed(
            seedColor: Colors.indigo,
            brightness: Brightness.light,
          ),
          appBarTheme: const AppBarTheme(centerTitle: false, elevation: 0),
          cardTheme:
              const CardThemeData(elevation: 1, margin: EdgeInsets.zero),
        ),
        home: const SplashScreen(),
      ),
    );
  }
}
