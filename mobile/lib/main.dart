import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'providers/auth_provider.dart';
import 'providers/compliance_provider.dart';
import 'providers/inspection_log_provider.dart';
import 'providers/inspection_provider.dart';
import 'providers/pending_complaints_provider.dart';
import 'providers/scan_provider.dart';
import 'screens/splash_screen.dart';
import 'services/settings_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Load the saved backend URL before any provider builds an ApiService,
  // so the very first request already uses the user's override.
  await SettingsService.load();
  runApp(const FieldProofApp());
}

class FieldProofApp extends StatelessWidget {
  const FieldProofApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ComplianceProvider()),
        ChangeNotifierProvider(create: (_) => InspectionProvider()),
        ChangeNotifierProvider(create: (_) => ScanProvider()),
        ChangeNotifierProvider(create: (_) => InspectionLogProvider()),
        ChangeNotifierProvider(create: (_) => PendingComplaintsProvider()),
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
          appBarTheme: const AppBarTheme(
            centerTitle: false,
            elevation: 0,
          ),
          cardTheme: const CardThemeData(
            elevation: 1,
            margin: EdgeInsets.zero,
          ),
        ),
        home: const SplashScreen(),
      ),
    );
  }
}
