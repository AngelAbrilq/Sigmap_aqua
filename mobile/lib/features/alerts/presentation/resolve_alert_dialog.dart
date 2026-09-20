import 'package:flutter/material.dart';

import '../data/alert.dart';

/// Pide la acción tomada antes de resolver. Devuelve `null` si se cancela.
Future<String?> showResolveAlertDialog(BuildContext context, Alert alert) =>
    showDialog<String>(
      context: context,
      builder: (context) => _ResolveAlertDialog(alert: alert),
    );

class _ResolveAlertDialog extends StatefulWidget {
  const _ResolveAlertDialog({required this.alert});

  final Alert alert;

  @override
  State<_ResolveAlertDialog> createState() => _ResolveAlertDialogState();
}

class _ResolveAlertDialogState extends State<_ResolveAlertDialog> {
  static const _minLength = 5;

  final _formKey = GlobalKey<FormState>();
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    if (_formKey.currentState?.validate() ?? false) {
      Navigator.pop(context, _controller.text.trim());
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Resolver alerta'),
      content: Form(
        key: _formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.alert.message),
            const SizedBox(height: 16),
            TextFormField(
              controller: _controller,
              autofocus: true,
              minLines: 2,
              maxLines: 4,
              maxLength: 500,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Acción tomada',
                hintText: 'Ej.: se encendió el aireador 2 y se recambió 20 % del agua',
              ),
              validator: (value) => (value?.trim().length ?? 0) < _minLength
                  ? 'Describe la acción tomada (mínimo $_minLength caracteres).'
                  : null,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        FilledButton(onPressed: _submit, child: const Text('Resolver')),
      ],
    );
  }
}
