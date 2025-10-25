from django.db import migrations, models
import ckeditor.fields


class Migration(migrations.Migration):

    dependencies = [
        ('membership', '0045_subscription_payment_method_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eltanconference',
            name='description',
            field=ckeditor.fields.RichTextField(),
        ),
        migrations.AddField(
            model_name='eltanconference',
            name='abstract_form_link',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='eltanconference',
            name='cfp_guidelines',
            field=ckeditor.fields.RichTextField(blank=True, help_text='Call for papers guidelines/content (HTML allowed)'),
        ),
        migrations.AddField(
            model_name='eltanconference',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='eltanconference',
            name='contact_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='eltanconference',
            name='contact_phone',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='eltanconference',
            name='sub_themes',
            field=ckeditor.fields.RichTextField(blank=True, help_text='List of sub-themes (HTML allowed)'),
        ),
        migrations.CreateModel(
            name='ConferenceLocMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('role', models.CharField(help_text='Committee role e.g. Chair, Media, Technical', max_length=200)),
                ('organization', models.CharField(blank=True, max_length=300)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('image', models.ImageField(blank=True, null=True, upload_to='conference_loc/')),
                ('order', models.IntegerField(default=0)),
                ('conference', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='loc_members', to='membership.eltanconference')),
            ],
            options={
                'ordering': ['order', 'name'],
                'verbose_name': 'LOC Member',
                'verbose_name_plural': 'LOC Members',
            },
        ),
    ]
