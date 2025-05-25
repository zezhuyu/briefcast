import 'package:flutter/material.dart';
import 'package:location/location.dart';
import 'music_player_screen.dart';
import 'search_page.dart';

class WelcomePage extends StatelessWidget {
  const WelcomePage({super.key});

  @override
  Widget build(BuildContext context) {
    // Get the screen size and orientation
    final size = MediaQuery.of(context).size;
    final orientation = MediaQuery.of(context).orientation;

    // Define breakpoints
    final isDesktop = size.width > 1024;
    final isTablet = size.width > 600 && size.width <= 1024;
    final isMobile = size.width <= 600;

    return Scaffold(
      backgroundColor: const Color(0xFF111218),
      body: SafeArea(
        child: Center(
          child: LayoutBuilder(
            builder: (context, constraints) {
              return Container(
                constraints: BoxConstraints(
                  maxWidth: isDesktop
                      ? 1200
                      : isTablet
                      ? 800
                      : double.infinity,
                ),
                padding: EdgeInsets.symmetric(
                  horizontal: isDesktop ? 48 : isTablet ? 32 : 16,
                  vertical: 24,
                ),
                child: _buildResponsiveLayout(
                  context,
                  isDesktop: isDesktop,
                  isTablet: isTablet,
                  isMobile: isMobile,
                  orientation: orientation,
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildResponsiveLayout(
      BuildContext context, {
        required bool isDesktop,
        required bool isTablet,
        required bool isMobile,
        required Orientation orientation,
      }) {
    if (isDesktop) {
      return _buildDesktopLayout(context);
    } else if (isTablet && orientation == Orientation.landscape) {
      return _buildTabletLayout(context);
    } else {
      return _buildMobileLayout(context);
    }
  }

  Widget _buildDesktopLayout(BuildContext context) {
    return Row(
      children: [
        Expanded(
          flex: 2,
          child: Image.asset(
            'images/3dicons.png',
            fit: BoxFit.contain,
          ),
        ),
        Expanded(
          flex: 3,
          child: _buildContent(
            context,
            titleSize: 60,
            subtitleSize: 32,
            buttonSize: 24,
          ),
        ),
      ],
    );
  }

  Widget _buildTabletLayout(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Image.asset(
            'images/3dicons.png',
            fit: BoxFit.contain,
          ),
        ),
        Expanded(
          child: _buildContent(
            context,
            titleSize: 50,
            subtitleSize: 28,
            buttonSize: 20,
          ),
        ),
      ],
    );
  }

  Widget _buildMobileLayout(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _buildTitle(40),
          const SizedBox(height: 80),
          Image.asset(
            'images/3dicons.png',
            height: MediaQuery.of(context).size.height * 0.3,
            fit: BoxFit.contain,
          ),
          const SizedBox(height: 40),
          _buildSubtitle(24),
          const SizedBox(height: 80),
          _buildButtons(context, 20),
        ],
      ),
    );
  }

  Widget _buildContent(
      BuildContext context, {
        required double titleSize,
        required double subtitleSize,
        required double buttonSize,
      }) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _buildTitle(titleSize),
        const SizedBox(height: 20),
        _buildSubtitle(subtitleSize),
        const SizedBox(height: 40),
        _buildButtons(context, buttonSize),
      ],
    );
  }

  Widget _buildTitle(double fontSize) {
    return Text(
      'BriefCast',
      style: TextStyle(
        color: Colors.white,
        fontSize: fontSize,
        fontWeight: FontWeight.bold,
      ),
    );
  }

  Widget _buildSubtitle(double fontSize) {
    return Text(
      'Your personal daily presidential briefing in the pocket',
      textAlign: TextAlign.center,
      style: TextStyle(
        color: Colors.white70,
        fontSize: fontSize,
      ),
    );
  }

  Widget _buildButtons(BuildContext context, double fontSize) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _buildButton(
              'Login',
              true,
              fontSize,
              () => Navigator.pushReplacement(
                context,
                MaterialPageRoute(builder: (context) => const MusicPlayerScreen(podcastId: '')),
              ),
            ),
            const SizedBox(width: 20),
            _buildButton('Sign up', false, fontSize, () {}),
          ],
        ),
        const SizedBox(height: 20),
        // _buildButton('Get Location', false, fontSize, () async {
        //   try {
        //     LocationData? locationData = await _getCurrentLocation();
        //     if (locationData != null && context.mounted) {
        //       ScaffoldMessenger.of(context).showSnackBar(
        //         SnackBar(
        //           content: Text(
        //             'Location: ${locationData.latitude}, ${locationData.longitude}',
        //           ),
        //         ),
        //       );
        //     }
        //   } catch (e) {
        //     if (context.mounted) {
        //       ScaffoldMessenger.of(context).showSnackBar(
        //         SnackBar(
        //           content: Text('Error: $e'),
        //         ),
        //       );
        //     }
        //   }
        // }),
      ],
    );
  }

  Widget _buildButton(
      String text,
      bool isPrimary,
      double fontSize,
      VoidCallback onTap,
      ) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: EdgeInsets.symmetric(
          horizontal: fontSize * 1.6,
          vertical: fontSize * 0.8,
        ),
        decoration: BoxDecoration(
          color: isPrimary ? const Color(0xFFEBD458) : null,
          border: !isPrimary
              ? Border.all(color: const Color(0xFFEBD458), width: 2)
              : null,
          borderRadius: BorderRadius.circular(60),
        ),
        child: Text(
          text,
          style: TextStyle(
            color: isPrimary
                ? const Color(0xFF111218)
                : const Color(0xFFEBD458),
            fontSize: fontSize,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}

Future<LocationData?> _getCurrentLocation() async {
  Location location = Location();

  bool serviceEnabled;
  PermissionStatus permissionGranted;

  // Check if service is enabled
  serviceEnabled = await location.serviceEnabled();
  if (!serviceEnabled) {
    serviceEnabled = await location.requestService();
    if (!serviceEnabled) {
      return null;
    }
  }

  // Check permissions
  permissionGranted = await location.hasPermission();
  if (permissionGranted == PermissionStatus.denied) {
    permissionGranted = await location.requestPermission();
    if (permissionGranted != PermissionStatus.granted) {
      return null;
    }
  }

  // Get location
  return await location.getLocation();
}