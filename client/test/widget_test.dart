// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';

import 'package:ai_judge_client/main.dart';

void main() {
  testWidgets('Judge home renders initial UI', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const JudgeApp());

    // Verify key UI elements are present.
    expect(find.text('AI 판사'), findsOneWidget);
    expect(find.text('사연을 들려주세요'), findsOneWidget);
    expect(find.text('판단 요청'), findsOneWidget);
    expect(find.text('결과가 여기 표시됩니다.'), findsOneWidget);
  });
}
