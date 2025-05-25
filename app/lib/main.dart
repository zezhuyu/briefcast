import 'package:flutter/material.dart';
// import 'package:webview_flutter/webview_flutter.dart';
import 'package:intl/intl.dart';
import 'package:location/location.dart';
import 'dart:developer' as developer;
import 'package:just_audio/just_audio.dart';
import 'package:cached_network_image/cached_network_image.dart';
import './pages/search_page.dart';
import './pages/welcome_page.dart';
import 'package:clerk_flutter/clerk_flutter.dart';

void main() {
  const publishableKey = String.fromEnvironment('CLERK_PUBLISHABLE_KEY');
  
  runApp(
    ClerkAuth(
      publishableKey: publishableKey,
      child: const MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFEBD458),
          brightness: Brightness.dark,
        ),
      ),
      home: const WelcomePage(),
    );
  }
}




