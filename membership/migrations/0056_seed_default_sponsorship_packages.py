from django.db import migrations

DEFAULT_PACKAGES = [
    {
        'tier': 'platinum',
        'tier_label': 'Platinum Sponsor',
        'price_range': '₦700,000+',
        'is_featured': True,
        'cta_label': 'Become a Platinum Sponsor',
        'order': 1,
        'benefits': (
            "Recognition as Platinum Sponsor in all event materials\n"
            "Logo placement on all banners, posters, and digital promotions\n"
            "Full-page advert in the conference programme\n"
            "Speaking opportunity during the opening session\n"
            "Exhibition booth in premium location\n"
            "4 complimentary registrations\n"
            "Social media recognition before, during, and after the event\n"
            "Company materials included in participant bags"
        ),
    },
    {
        'tier': 'gold',
        'tier_label': 'Gold Sponsor',
        'price_range': '₦500,000 – ₦699,000',
        'is_featured': False,
        'cta_label': 'Become a Gold Sponsor',
        'order': 2,
        'benefits': (
            "Recognition as Gold Sponsor in event materials\n"
            "Logo on banners, posters, and digital promotions\n"
            "Half-page advert in the programme\n"
            "Exhibition booth\n"
            "2 complimentary registrations\n"
            "Social media shoutouts\n"
            "Company materials included in participant bags"
        ),
    },
    {
        'tier': 'silver',
        'tier_label': 'Silver Sponsor',
        'price_range': '₦350,000 – ₦499,000',
        'is_featured': False,
        'cta_label': 'Become a Silver Sponsor',
        'order': 3,
        'benefits': (
            "Recognition as Silver Sponsor\n"
            "Logo on event website and select materials\n"
            "Quarter-page advert in the programme\n"
            "1 complimentary registration\n"
            "Shared exhibition space\n"
            "Mention on social media"
        ),
    },
    {
        'tier': 'bronze',
        'tier_label': 'Bronze Sponsor',
        'price_range': '₦150,000 – ₦349,000',
        'is_featured': False,
        'cta_label': 'Become a Bronze Sponsor',
        'order': 4,
        'benefits': (
            "Name listed in the programme and on the website\n"
            "Company materials displayed at registration\n"
            "Mention during the closing session"
        ),
    },
    {
        'tier': 'inkind',
        'tier_label': 'In-Kind Sponsorship',
        'price_range': 'Value-matched benefits',
        'is_featured': False,
        'cta_label': 'Express Interest',
        'order': 5,
        'benefits': (
            "ELTAN warmly welcomes non-cash contributions. In-kind sponsors receive benefits matched to the value of their contribution — including logo display, exhibition space, and formal acknowledgements.\n"
            "Acceptable contributions include: conference materials (e.g., bags, notepads, pens), refreshments and catering, technical support (AV equipment, printing, photography).\n"
            "Custom sponsorship packages are also available upon request. We are happy to design an arrangement that aligns with your organisation's specific goals and budget."
        ),
    },
]


def seed_packages(apps, schema_editor):
    EltanConference = apps.get_model('membership', 'EltanConference')
    SponsorshipPackage = apps.get_model('membership', 'SponsorshipPackage')

    for conference in EltanConference.objects.all():
        # Only seed if the conference has no packages yet
        if not SponsorshipPackage.objects.filter(conference=conference).exists():
            for pkg in DEFAULT_PACKAGES:
                SponsorshipPackage.objects.create(conference=conference, **pkg)


def unseed_packages(apps, schema_editor):
    SponsorshipPackage = apps.get_model('membership', 'SponsorshipPackage')
    # Only remove entries that exactly match the seeded data to avoid destroying
    # any packages an admin may have manually edited
    for pkg in DEFAULT_PACKAGES:
        SponsorshipPackage.objects.filter(
            tier=pkg['tier'],
            tier_label=pkg['tier_label'],
            price_range=pkg['price_range'],
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('membership', '0055_add_sponsorship_package_and_accommodation'),
    ]

    operations = [
        migrations.RunPython(seed_packages, reverse_code=unseed_packages),
    ]
