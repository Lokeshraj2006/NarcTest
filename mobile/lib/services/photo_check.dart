import 'dart:typed_data';
import 'dart:ui' as ui;

/// Quick sharpness check on the phone, right after the photo is taken.
///
/// Looks only at the band where the colour card sits (the yellow guide box) and measures
/// how much the brightness changes from pixel to pixel (Laplacian variance). Blurry or very
/// dark photos score low. The limit was set using our 19 real phone photos (29 Sep 2026):
/// blurry ones scored 58-180, good ones 337 and above.
class PhotoCheck {
  static const double blurLimit = 230;

  static Future<double> sharpness(Uint8List jpeg) async {
    final codec = await ui.instantiateImageCodec(jpeg, targetWidth: 360);
    final image = (await codec.getNextFrame()).image;
    final data = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
    final w = image.width, h = image.height;
    image.dispose();
    if (data == null || w < 3 || h < 3) return double.infinity;

    final y0 = (h * 0.20).floor(), y1 = (h * 0.62).floor();
    final rows = y1 - y0;
    final gray = Float64List(w * rows);
    for (var y = 0; y < rows; y++) {
      for (var x = 0; x < w; x++) {
        final i = ((y + y0) * w + x) * 4;
        gray[y * w + x] = 0.299 * data.getUint8(i) + 0.587 * data.getUint8(i + 1) + 0.114 * data.getUint8(i + 2);
      }
    }
    var sum = 0.0, sumSq = 0.0, n = 0;
    for (var y = 1; y < rows - 1; y++) {
      for (var x = 1; x < w - 1; x++) {
        final c = y * w + x;
        final lap = gray[c - 1] + gray[c + 1] + gray[c - w] + gray[c + w] - 4 * gray[c];
        sum += lap;
        sumSq += lap * lap;
        n++;
      }
    }
    if (n == 0) return double.infinity;
    final mean = sum / n;
    return sumSq / n - mean * mean;
  }

  static Future<bool> looksBlurry(Uint8List jpeg) async {
    try {
      return await sharpness(jpeg) < blurLimit;
    } catch (_) {
      return false; // never block the officer because the check itself failed
    }
  }
}
