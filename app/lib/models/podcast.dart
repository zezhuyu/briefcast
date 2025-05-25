class Podcast {
  final String id;
  final String title;
  final String author;
  final String description;
  final String imageUrl;
  final String audioUrl;
  final String publishDate;

  Podcast({
    required this.id,
    required this.title,
    required this.author,
    required this.description,
    required this.imageUrl,
    required this.audioUrl,
    required this.publishDate,
  });

  factory Podcast.fromJson(Map<String, dynamic> json) {
    return Podcast(
      id: json['id'],
      title: json['title'],
      author: json['author'],
      description: json['description'],
      imageUrl: json['imageUrl'],
      audioUrl: json['audioUrl'],
      publishDate: json['publishDate'],
    );
  }
} 