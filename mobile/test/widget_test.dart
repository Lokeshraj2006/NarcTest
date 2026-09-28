// Smoke test — the app builds its first frame without throwing.
//
// SplashScreen schedules an 800 ms delay before routing, so the test must
// pump past it; a timer still pending when the tree is disposed fails the
// test binding. Session lookup hits flutter_secure_storage, which has no
// plugin in the test host — AuthProvider.checkSession swallows that, which
// is the behaviour we want to confirm survives.

import 'package:flutter_test/flutter_test.dart';

import 'package:labelguard_mobile/main.dart';

void main() {
  testWidgets('App builds and shows its brand without throwing',
      (WidgetTester tester) async {
    await tester.pumpWidget(const FieldProofApp());

    expect(find.text('FieldProof'), findsOneWidget);

    // Drain the splash timer and the routing frame that follows it.
    await tester.pump(const Duration(seconds: 1));
    await tester.pump();
  });
}
