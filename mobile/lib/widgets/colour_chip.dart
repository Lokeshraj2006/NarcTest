import 'package:flutter/material.dart';

import '../l10n/lang.dart';

import '../utils/app_colors.dart';

/// A small colour square with a label under it.
class ColourChip extends StatelessWidget {
  final Color? color;
  final String label;
  final bool highlight;
  final double size;

  const ColourChip({
    super.key,
    required this.color,
    required this.label,
    this.highlight = false,
    this.size = 48,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size + 40,
      child: Column(
        children: [
          Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              color: color ?? Colors.grey.shade300,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: highlight ? Colors.black87 : AppColors.border,
                width: highlight ? 3 : 1,
              ),
            ),
            child: color == null
                ? const Icon(Icons.help_outline, color: Colors.black38)
                : null,
          ),
          const SizedBox(height: 4),
          Text(
            label,
            textAlign: TextAlign.center,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 11,
              fontWeight: highlight ? FontWeight.bold : FontWeight.normal,
            ),
          ),
        ],
      ),
    );
  }
}

/// Coloured pill for POSITIVE / NEGATIVE / INCONCLUSIVE.
class ResultPill extends StatelessWidget {
  final String result;
  const ResultPill({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    final r = result.toUpperCase();
    final text = r == 'INCONCLUSIVE' ? tr(context, 'NOT SURE') : r;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.forResult(r),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(text,
          style: const TextStyle(
              color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12)),
    );
  }
}
