import 'package:flutter/material.dart';

/// Pill badge for compliance and rule check verdicts.
class StatusBadge extends StatelessWidget {
  final String status;
  final double fontSize;

  const StatusBadge({
    super.key,
    required this.status,
    this.fontSize = 12,
  });

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color fg;
    String label;

    switch (status.toUpperCase()) {
      case 'PASS':
      case 'COMPLIANT':
        bg = Colors.green.shade50;
        fg = Colors.green.shade700;
        label = 'COMPLIANT';
        break;
      case 'FAIL':
      case 'VIOLATION':
        bg = Colors.red.shade50;
        fg = Colors.red.shade700;
        label = 'VIOLATION';
        break;
      case 'REVIEW':
      case 'REVIEW_NEEDED':
        bg = Colors.amber.shade50;
        fg = Colors.amber.shade800;
        label = 'REVIEW';
        break;
      case 'NEEDS_REVIEW':
        bg = Colors.amber.shade50;
        fg = Colors.amber.shade800;
        label = 'NEEDS REVIEW';
        break;
      case 'EXEMPT':
        bg = Colors.blue.shade50;
        fg = Colors.blue.shade700;
        label = 'EXEMPT';
        break;
      default:
        bg = Colors.grey.shade100;
        fg = Colors.grey.shade700;
        label = status.toUpperCase();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: fg.withValues(alpha: 0.3), width: 1),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: fg,
          fontSize: fontSize,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}
