import 'package:ntp/ntp.dart';

/// Queries atomic NTP servers to obtain tamper-proof reference timestamps.
class NtpService {
  static const String defaultNtpServer = 'pool.ntp.org';
  static const int timeoutMs = 4000;

  /// Fetch true atomic time from NTP pool.
  /// Falls back to local device time if network is unavailable, noting drift as null.
  static Future<NtpTimeResult> getNetworkTime({String server = defaultNtpServer}) async {
    final deviceTime = DateTime.now().toUtc();
    try {
      final ntpTime = await NTP.now(
        lookUpAddress: server,
        timeout: const Duration(milliseconds: timeoutMs),
      );
      final ntpUtc = ntpTime.toUtc();
      final driftSeconds = (deviceTime.difference(ntpUtc).inMilliseconds.abs()) / 1000.0;

      return NtpTimeResult(
        deviceTime: deviceTime,
        ntpTime: ntpUtc,
        driftSeconds: driftSeconds,
        isSuccess: true,
      );
    } catch (e) {
      return NtpTimeResult(
        deviceTime: deviceTime,
        ntpTime: null,
        driftSeconds: null,
        isSuccess: false,
        error: e.toString(),
      );
    }
  }
}

class NtpTimeResult {
  final DateTime deviceTime;
  final DateTime? ntpTime;
  final double? driftSeconds;
  final bool isSuccess;
  final String? error;

  NtpTimeResult({
    required this.deviceTime,
    this.ntpTime,
    this.driftSeconds,
    required this.isSuccess,
    this.error,
  });
}
