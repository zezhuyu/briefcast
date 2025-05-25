import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:intl/intl.dart';
import 'dart:developer' as developer;
import '../models/podcast.dart';
import 'search_page.dart';

class MusicPlayerScreen extends StatefulWidget {
  final String podcastId;
  const MusicPlayerScreen({super.key, required this.podcastId});

  @override
  State<MusicPlayerScreen> createState() {
    developer.log('Loading podcast with ID: $podcastId');
    return _MusicPlayerScreenState();
  }
}

class _MusicPlayerScreenState extends State<MusicPlayerScreen> {
  final AudioPlayer _audioPlayer = AudioPlayer();
  bool isPlaying = false;
  Duration _duration = Duration.zero;
  Duration _position = Duration.zero;
  Podcast? podcast;
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadPodcast();
    _audioPlayer.playerStateStream.listen((state) {
      setState(() {
        isPlaying = state.playing;
      });
    });
  }

  Future<void> _loadPodcast() async {
    try {
      // For testing, use mock data
      await Future.delayed(const Duration(seconds: 1)); // Simulate network delay
      final mockPodcast = {
        'id': widget.podcastId,
        'title': 'Daily Briefing',
        'author': 'BriefCast',
        'description': 'Your daily presidential briefing',
        'imageUrl': 'https://picsum.photos/400',
        'audioUrl': 'https://briefcast_app.samappx.com/generate',
        'publishDate': DateTime.now().toIso8601String(),
      };

      // Comment out the real API call for now
      /*
      final response = await http.get(
        Uri.parse('https://example.com/podcasts/${widget.podcastId}'),
      );
      if (!mounted) return;
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          podcast = Podcast.fromJson(data);
          isLoading = false;
        });
      } else {
        throw Exception('Failed to load podcast');
      }
      */

      if (!mounted) return;
      setState(() {
        podcast = Podcast.fromJson(mockPodcast);
        isLoading = false;
      });

      await _setupAudioPlayer();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading podcast: $e')),
      );
    }
  }

  Future<void> _setupAudioPlayer() async {
    try {
      await _audioPlayer.setUrl(podcast?.audioUrl ?? '');
      
      _audioPlayer.durationStream.listen((d) {
        setState(() => _duration = d ?? Duration.zero);
      });

      _audioPlayer.positionStream.listen((p) {
        setState(() => _position = p);
      });
    } catch (e) {
      developer.log('Error setting up audio: $e');
    }
  }

  // Update play/pause handler
  Future<void> _handlePlayPause() async {
    try {
      if (isPlaying) {
        await _audioPlayer.pause();
      } else {
        await _audioPlayer.play();
      }
      setState(() {
        isPlaying = !isPlaying;
      });
    } catch (e) {
      developer.log('Error playing audio: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error playing audio: $e')),
        );
      }
    }
  }

  // Update reloadAudio method
  Future<void> reloadAudio() async {
    await _audioPlayer.stop();
    await _audioPlayer.seek(Duration.zero);
    setState(() {
      isPlaying = false;
      _position = Duration.zero;
    });
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  String _formatDuration(Duration duration) {
    String twoDigits(int n) => n.toString().padLeft(2, '0');
    final minutes = twoDigits(duration.inMinutes.remainder(60));
    final seconds = twoDigits(duration.inSeconds.remainder(60));
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Scaffold(
        backgroundColor: Color(0xFF111218),
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    if (podcast == null) {
      return const Scaffold(
        backgroundColor: Color(0xFF111218),
        body: Center(
          child: Text(
            'Failed to load podcast',
            style: TextStyle(color: Colors.white),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFF111218),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16.0),
          child: Column(
            children: [
              _buildHeader(),
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    children: [
                      _buildAlbumArt(),
                      const SizedBox(height: 24),
                      _buildSongInfo(),
                    ],
                  ),
                ),
              ),
              _buildPlayerControls(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => SearchPage()),
            ),
          ),
          Text(
            podcast?.title ?? 'BriefCast',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.w500,
            ),
          ),
          IconButton(
            icon: const Icon(Icons.more_vert, color: Colors.white),
            onPressed: () {},
          ),
        ],
      ),
    );
  }

  Widget _buildAlbumArt() {
    final size = MediaQuery.of(context).size.width - 32; // Full width minus margins
    final fixedSize = 350.0; // Or any other fixed size you want

    return Container(
      width: fixedSize,
      height: fixedSize,
      margin: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(60),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF6F25A0).withOpacity(0.2),
            blurRadius: 100,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(60),
        child: CachedNetworkImage(
          imageUrl: podcast?.imageUrl ?? '',
          placeholder: (context, url) => const Center(
            child: CircularProgressIndicator(),
          ),
          errorWidget: (context, url, error) => Image.asset(
            'images/gr.png',
            fit: BoxFit.cover,
          ),
          fit: BoxFit.cover,
          width: fixedSize,
          height: fixedSize,
        ),
      ),
    );
  }

  Widget _buildSongInfo() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24.0),
      child: Column(
        children: [
          const SizedBox(height: 8),
          Text(
            podcast?.author ?? 'Loading...',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            podcast?.publishDate != null 
                ? DateFormat('MMM d, yyyy').format(DateTime.parse(podcast!.publishDate))
                : DateFormat('MMM d, yyyy').format(DateTime.now()),
            style: const TextStyle(
              color: Colors.white70,
              fontSize: 16,
            ),
          ),
          if (podcast?.description != null) ...[
            const SizedBox(height: 16),
            Text(
              podcast!.description,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 14,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildPlayerControls(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildTimeProgress(),
          const SizedBox(height: 8),
          _buildAudioVisualizer(context),
          // _buildProgressBar(context),
          const SizedBox(height: 16),
          _buildControls(),
        ],
      ),
    );
  }

  Widget _buildTimeProgress() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            _formatDuration(_position),
            style: const TextStyle(color: Colors.white70),
          ),
          Text(
            _formatDuration(_duration),
            style: const TextStyle(color: Colors.white70),
          ),
        ],
      ),
    );
  }

  Widget _buildControls() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: [
        IconButton(
          icon: const Icon(Icons.shuffle, color: Colors.white70),
          onPressed: () {},
        ),
        IconButton(
          icon: const Icon(Icons.skip_previous, color: Colors.white, size: 36),
          onPressed: () => reloadAudio(),  // Add reload functionality
        ),
        IconButton(
          icon: Icon(
            isPlaying ? Icons.pause_circle_filled : Icons.play_circle_fill,
            color: Colors.white,
            size: 64,
          ),
          onPressed: _handlePlayPause,  // Use the new handler
        ),
        IconButton(
          icon: const Icon(Icons.skip_next, color: Colors.white, size: 36),
          onPressed: () {},
        ),
        IconButton(
          icon: const Icon(Icons.repeat, color: Colors.white70),
          onPressed: () {},
        ),
      ],
    );
  }

  Widget _buildProgressBar(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 24.0),
      child: SliderTheme(
        data: SliderTheme.of(context).copyWith(
          thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 4),
          trackHeight: 4,
          trackShape: const RoundedRectSliderTrackShape(),
        ),
        child: Slider(
          value: _position.inSeconds.toDouble(),
          max: _duration.inSeconds.toDouble(),
          min: 0,
          activeColor: Theme.of(context).colorScheme.primary,
          inactiveColor: Colors.white24,
          onChanged: (value) async {
            final position = Duration(seconds: value.toInt());
            await _audioPlayer.seek(position);
          },
        ),
      ),
    );
  }

  Widget _buildAudioVisualizer(BuildContext context) {
    final primaryColor = Theme.of(context).colorScheme.primary;
    final numBars = 40;
    final progress = _duration.inSeconds > 0 
        ? _position.inSeconds / _duration.inSeconds 
        : 0.0;
    final activeBarCount = (progress * numBars).round();

    void seekToPosition(Offset localPosition) {
      final box = context.findRenderObject() as RenderBox;
      final pos = localPosition.dx;
      final percent = pos / box.size.width;
      final newPosition = Duration(
        seconds: (percent * _duration.inSeconds).round(),
      );
      _audioPlayer.seek(newPosition);
    }

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        onTapDown: (details) => seekToPosition(details.localPosition),
        onHorizontalDragUpdate: (details) => seekToPosition(details.localPosition),
        child: Container(
          height: 50,
          margin: const EdgeInsets.symmetric(vertical: 24),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.00),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: List.generate(
              numBars,
              (index) => Container(
                width: 1.5,
                height: 20 + (index % 3) * 10,
                decoration: BoxDecoration(
                  color: index < activeBarCount ? primaryColor : Colors.white24,
                  borderRadius: BorderRadius.circular(0.75),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}