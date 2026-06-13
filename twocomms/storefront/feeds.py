"""RSS feed for the TwoComms blog.

SEO / AI-discovery 2026-06-11: an RSS feed lets Google Discover, news
aggregators and LLM crawlers subscribe to new blog content (the blog is
the main vehicle for informational-intent SEO). Kept intentionally
simple — only published posts, newest first.
"""

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed
from django.utils.html import strip_tags
from django.utils.text import Truncator

from .models import BlogPost


class BlogRssFeed(Feed):
    feed_type = Rss201rev2Feed
    title = "TwoComms — блог про стрітвір та мілітарі-одяг"
    description = (
        "Нові статті TwoComms: гайди по догляду за одягом з DTF-друком, "
        "розмірні сітки, історії принтів та новини бренду."
    )

    def link(self):
        return reverse("blog")

    def items(self):
        return (
            BlogPost.objects.filter(is_published=True)
            .order_by("-published_at")[:20]
        )

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        if item.excerpt:
            return item.excerpt
        return Truncator(strip_tags(item.content_html or "")).chars(300)

    def item_link(self, item):
        return reverse("blog_post", kwargs={"slug": item.slug})

    def item_pubdate(self, item):
        return item.published_at
