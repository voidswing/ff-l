import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const JudgeApp());
}

class JudgeApp extends StatelessWidget {
  const JudgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI 판사',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0E5E6F)),
        textTheme: GoogleFonts.notoSansKrTextTheme(),
        useMaterial3: true,
      ),
      home: const JudgeHomePage(),
    );
  }
}

class JudgeHomePage extends StatefulWidget {
  const JudgeHomePage({super.key});

  @override
  State<JudgeHomePage> createState() => _JudgeHomePageState();
}

class _JudgeHomePageState extends State<JudgeHomePage> {
  final TextEditingController _controller = TextEditingController();
  bool _loading = false;
  JudgmentResponse? _response;
  String? _error;

  String get _apiBaseUrl {
    if (kIsWeb) {
      return 'http://localhost:8000';
    }
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://localhost:8000';
  }

  Future<void> _submit() async {
    final story = _controller.text.trim();
    if (story.isEmpty) {
      setState(() {
        _error = '사연을 입력해 주세요.';
        _response = null;
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
      _response = null;
    });

    try {
      final response = await http.post(
        Uri.parse('$_apiBaseUrl/api/judge'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'story': story}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        setState(() {
          _response = JudgmentResponse.fromJson(data as Map<String, dynamic>);
        });
      } else {
        setState(() {
          _error = '요청 실패: ${response.statusCode}';
        });
      }
    } catch (e) {
      setState(() {
        _error = '오류 발생: $e';
      });
    } finally {
      setState(() {
        _loading = false;
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI 판사'),
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFFF5FBFD), Color(0xFFFDF7F2)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '사연을 들려주세요',
                  style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 6),
                Text(
                  'AI가 가능한 죄명과 근거를 요약해 드립니다.',
                  style: theme.textTheme.bodyMedium?.copyWith(color: Colors.black54),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _controller,
                  maxLines: 6,
                  decoration: const InputDecoration(
                    labelText: '사연을 입력하세요',
                    border: OutlineInputBorder(),
                    filled: true,
                    fillColor: Colors.white,
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _loading ? null : _submit,
                    child: _loading
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('판단 요청'),
                  ),
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: _buildResultCard(theme),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildResultCard(ThemeData theme) {
    final response = _response;
    if (_loading) {
      return _cardShell(
        child: const Center(child: CircularProgressIndicator()),
      );
    }
    if (_error != null) {
      return _cardShell(
        child: Text(
          _error!,
          style: theme.textTheme.bodyLarge?.copyWith(color: Colors.redAccent),
        ),
      );
    }
    if (response == null) {
      return _cardShell(
        child: Text(
          '결과가 여기 표시됩니다.',
          style: theme.textTheme.bodyMedium?.copyWith(color: Colors.black54),
        ),
      );
    }

    return _cardShell(
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('요약'),
            const SizedBox(height: 6),
            Text(response.summary),
            const SizedBox(height: 16),
            _sectionTitle('가능한 죄'),
            const SizedBox(height: 8),
            if (response.possibleCrimes.isEmpty)
              Text('없음 또는 판단 보류', style: theme.textTheme.bodyMedium),
            if (response.possibleCrimes.isNotEmpty)
              ...response.possibleCrimes.map(
                (crime) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _crimeChip(crime),
                ),
              ),
            const SizedBox(height: 12),
            _sectionTitle('판단'),
            const SizedBox(height: 6),
            Text(response.verdict),
            const SizedBox(height: 16),
            Text(
              response.disclaimer,
              style: theme.textTheme.bodySmall?.copyWith(color: Colors.black54),
            ),
          ],
        ),
      ),
    );
  }

  Widget _cardShell({required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        boxShadow: const [
          BoxShadow(
            color: Color(0x1A000000),
            blurRadius: 12,
            offset: Offset(0, 4),
          ),
        ],
      ),
      child: child,
    );
  }

  Widget _sectionTitle(String text) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w700,
      ),
    );
  }

  Widget _crimeChip(Crime crime) {
    final color = switch (crime.severity) {
      '중대' => const Color(0xFFE53935),
      '중간' => const Color(0xFFFB8C00),
      _ => const Color(0xFF43A047),
    };
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.25)),
        color: color.withOpacity(0.08),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  crime.title,
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
              Text(
                crime.severity,
                style: TextStyle(color: color, fontWeight: FontWeight.w600),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(crime.basis),
        ],
      ),
    );
  }
}

class JudgmentResponse {
  JudgmentResponse({
    required this.summary,
    required this.possibleCrimes,
    required this.verdict,
    required this.disclaimer,
  });

  final String summary;
  final List<Crime> possibleCrimes;
  final String verdict;
  final String disclaimer;

  factory JudgmentResponse.fromJson(Map<String, dynamic> json) {
    final crimesJson = json['possible_crimes'] as List<dynamic>? ?? [];
    return JudgmentResponse(
      summary: (json['summary'] ?? '').toString(),
      possibleCrimes: crimesJson
          .map((item) => Crime.fromJson(item as Map<String, dynamic>))
          .toList(),
      verdict: (json['verdict'] ?? '').toString(),
      disclaimer: (json['disclaimer'] ?? '').toString(),
    );
  }
}

class Crime {
  Crime({
    required this.title,
    required this.basis,
    required this.severity,
  });

  final String title;
  final String basis;
  final String severity;

  factory Crime.fromJson(Map<String, dynamic> json) {
    return Crime(
      title: (json['title'] ?? '').toString(),
      basis: (json['basis'] ?? '').toString(),
      severity: (json['severity'] ?? '').toString(),
    );
  }
}
