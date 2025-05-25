import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import './music_player_screen.dart';


class SearchPage extends StatefulWidget {
  @override
  _SearchPageState createState() => _SearchPageState();
}

class _SearchPageState extends State<SearchPage> {
  List<dynamic> recentPlays = [];
  List<dynamic> podcasts = [];

  @override
  void initState() {
    super.initState();
    // Comment out real API fetch
    // _fetchData();
    _loadMockData();
  }

  void _loadMockData() {
    setState(() {
      recentPlays = [
        {
          'id': '1',
          'title': 'Tech Talk Weekly',
          'author': 'John Doe',
          'imageUrl': 'https://picsum.photos/200',
        },
        {
          'id': '2',
          'title': 'Science Today',
          'author': 'Jane Smith',
          'imageUrl': 'https://picsum.photos/201',
        },
        {
          'id': '3',
          'title': 'Daily News',
          'author': 'Mike Johnson',
          'imageUrl': 'https://picsum.photos/202',
        },
      ];

      podcasts = [
        {
          'id': '1',
          'title': 'Flutter Development',
          'author': 'Dev Team',
          'description': 'Learn Flutter development from scratch',
          'imageUrl': 'https://picsum.photos/203',
        },
        {
          'id': '2',
          'title': 'Mobile App Design',
          'author': 'Design Masters',
          'description': 'Ultimate guide to mobile UI/UX',
          'imageUrl': 'https://picsum.photos/204',
        },
      ];
    });
  }

  // Commented out real API fetch
  /*
  Future<void> _fetchData() async {
    try {
      final playedResponse = await http.get(Uri.parse('https://example.com/played'));
      final recommendResponse = await http.get(Uri.parse('https://example.com/recommand'));

      if (mounted) {
        setState(() {
          recentPlays = jsonDecode(playedResponse.body);
          podcasts = jsonDecode(recommendResponse.body);
        });
      }
    } catch (e) {
      print('Error fetching data: $e');
    }
  }
  */

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF11121F),
      body: SafeArea(
        child: Column(
          children: [
            // Status Bar (Fixed)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Container(
                height: 48,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.06),
                  borderRadius: BorderRadius.circular(40),
                ),
                child: Row(
                  children: [
                    const SizedBox(width: 22),
                    Icon(Icons.search, color: Colors.white.withOpacity(0.4)),
                    const SizedBox(width: 14),
                    Text(
                      'Search',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.4),
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // Scrollable Content
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Recent Plays - Horizontal List
                    const Padding(
                      padding: EdgeInsets.only(left: 17, top: 30, bottom: 16),
                      child: Text(
                        'Recent Plays',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    SizedBox(
                      height: 80,
                      child: ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 17),
                        scrollDirection: Axis.horizontal,
                        itemCount: recentPlays.length,
                        itemBuilder: (context, index) {
                          return _buildRecentPlayItem(recentPlays[index]);
                        },
                      ),
                    ),

                    // Podcasts - Vertical List
                    const Padding(
                      padding: EdgeInsets.only(left: 17, top: 30, bottom: 16),
                      child: Text(
                        'For You',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 17),
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: podcasts.length,
                      itemBuilder: (context, index) {
                        return _buildPodcastListItem(podcasts[index]);
                      },
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRecentPlayItem(dynamic playData) {
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => MusicPlayerScreen(podcastId: playData['id']),
          ),
        );
      },
      child: Padding(
        padding: const EdgeInsets.only(right: 12),
        child: Container(
          width: 240,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.06),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(12),
                  bottomLeft: Radius.circular(12),
                ),
                child: Image.network(
                  playData['imageUrl'],
                  width: 80,
                  height: 80,
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      playData['title'],
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      playData['author'],
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.6),
                        fontSize: 14,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPodcastListItem(dynamic podcastData) {
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => MusicPlayerScreen(podcastId: podcastData['id']),
          ),
        );
      },
      child: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Container(
          height: 100,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.06),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(12),
                  bottomLeft: Radius.circular(12),
                ),
                child: Image.network(
                  podcastData['imageUrl'],
                  width: 100,
                  height: 100,
                  fit: BoxFit.cover,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      podcastData['title'],
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      podcastData['author'],
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.6),
                        fontSize: 14,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      podcastData['description'],
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.4),
                        fontSize: 12,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 16),
            ],
          ),
        ),
      ),
    );
  }
} 