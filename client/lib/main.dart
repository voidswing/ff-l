import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:http/http.dart' as http;

const String _apiBaseUrlFromDefine = String.fromEnvironment('API_BASE_URL');
const int _storyMinLength = 3;
const int _storyMaxLength = 5000;
const Duration _requestTimeout = Duration(seconds: 20);

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
  int _storyLength = 0;
  bool _loading = false;
  JudgmentResponse? _response;
  String? _error;
  bool get _canSubmit => !_loading && _validateStory(_controller.text.trim()) == null;

  String get _apiBaseUrl {
    final fromDefine = _apiBaseUrlFromDefine.trim();
    if (fromDefine.isNotEmpty) {
      return fromDefine;
    }
    if (kIsWeb) {
      return 'http://localhost:8000';
    }
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://localhost:8000';
  }

  String? _validateStory(String story) {
    if (story.isEmpty) {
      return '사연을 입력해 주세요.';
    }
    if (story.length < _storyMinLength) {
      return '사연은 최소 $_storyMinLength자 이상 입력해 주세요.';
    }
    if (story.length > _storyMaxLength) {
      return '사연은 최대 $_storyMaxLength자까지 입력할 수 있습니다.';
    }
    return null;
  }

  String _extractServerErrorMessage(http.Response response) {
    final fallback = '요청 실패: ${response.statusCode}';
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is Map<String, dynamic>) {
        final detail = decoded['detail'];
        if (detail is String && detail.trim().isNotEmpty) {
          return detail;
        }
        if (detail is List && detail.isNotEmpty) {
          final first = detail.first;
          if (first is Map<String, dynamic>) {
            final message = first['msg'];
            if (message is String && message.trim().isNotEmpty) {
              return message;
            }
          }
        }
      }
    } catch (_) {}
    return fallback;
  }

  Future<void> _submit() async {
    final story = _controller.text.trim();
    final validationError = _validateStory(story);
    if (validationError != null) {
      setState(() {
        _error = validationError;
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
      ).timeout(_requestTimeout);

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        if (!mounted) {
          return;
        }
        setState(() {
          _response = JudgmentResponse.fromJson(data as Map<String, dynamic>);
        });
      } else {
        final message = _extractServerErrorMessage(response);
        if (!mounted) {
          return;
        }
        setState(() {
          _error = message;
        });
      }
    } catch (e) {
      if (e is TimeoutException) {
        if (!mounted) {
          return;
        }
        setState(() {
          _error = '요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.';
        });
        return;
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _error = '네트워크 오류가 발생했습니다: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
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
                  maxLength: _storyMaxLength,
                  onChanged: (value) {
                    setState(() {
                      _storyLength = value.length;
                    });
                  },
                  decoration: const InputDecoration(
                    labelText: '사연을 입력하세요',
                    border: OutlineInputBorder(),
                    filled: true,
                    fillColor: Colors.white,
                  ),
                ),
                Align(
                  alignment: Alignment.centerRight,
                  child: Text(
                    '$_storyLength/$_storyMaxLength',
                    style: theme.textTheme.bodySmall?.copyWith(color: Colors.black54),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _canSubmit ? _submit : null,
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
        border: Border.all(color: color.withValues(alpha: 0.25)),
        color: color.withValues(alpha: 0.08),
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
