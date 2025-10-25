# 🎛️ CMS Dynamic Content Guide - ELTAN Landing Page

## Overview

The new ELTAN landing page is **fully dynamic** and controlled through the Django Admin panel. Administrators can update all content without touching code.

---

## 🎨 What Can Be Managed from Admin

### 1. **Hero Section** (Homepage Slider)
**Admin Path**: `Core → Hero Slides`

**Fields to Manage**:
- ✅ Background image
- ✅ Title (e.g., "Welcome to ELTAN")
- ✅ Subtitle/Description
- ✅ CTA button text
- ✅ CTA button link
- ✅ Display order
- ✅ Active/Inactive toggle

**How It Works**:
- Add multiple hero slides for a carousel effect
- If no slides exist, shows default static hero
- Slides auto-rotate every 6 seconds
- Users can manually navigate with arrows

**Example**:
```
Title: "Join ELTAN Annual Conference 2025"
Subtitle: "Connect with educators nationwide"
CTA Text: "Register Now"
CTA Link: /conferences/
Background: [Upload conference image]
Order: 1
Is Active: ✅
```

---

### 2. **Statistics Section**
**Admin Path**: `Core → Statistics`

**Fields to Manage**:
- ✅ Number (e.g., "500+", "95%")
- ✅ Label (e.g., "Active Members")
- ✅ Material icon name (e.g., "people", "event")
- ✅ Background color (hex code)
- ✅ Display order
- ✅ Active/Inactive toggle

**Default Statistics** (if CMS empty):
1. 500+ Active Members
2. 12+ Annual Events
3. 36 State Chapters
4. 95% Satisfaction Rate

**Material Icons Reference**: https://fonts.google.com/icons

**Example**:
```
Number: 1,200+
Label: English Teachers
Icon: school
Color: #E67918 (optional - uses orange gradient if blank)
Order: 1
Is Active: ✅
```

---

### 3. **Features Section** (What We Offer)
**Admin Path**: `Core → Features`

**Fields to Manage**:
- ✅ Title
- ✅ Description (supports rich text)
- ✅ Icon (Material icon name) OR Image upload
- ✅ Link/URL
- ✅ Display order
- ✅ Active/Inactive toggle

**Default Features** (if CMS empty):
1. Conference & Exhibition
2. Volunteer Positions
3. Special Interest Groups
4. Jobs & Careers
5. PRELIM Resources
6. Professional Development

**Example**:
```
Title: "Teacher Training Workshops"
Description: "Monthly professional development workshops focusing on modern teaching methodologies and classroom management."
Icon: workspace_premium
Link: /events/
Order: 7
Is Active: ✅
```

---

### 4. **FAQ Section**
**Admin Path**: `Core → FAQs`

**Fields to Manage**:
- ✅ Question
- ✅ Answer (supports HTML/rich text)
- ✅ Display order
- ✅ Active/Inactive toggle

**Default FAQs** (if CMS empty):
1. How do I get started with ELTAN membership?
2. What are the membership fees?
3. What benefits do members receive?
4. How can I attend the annual conference?
5. Are there resources for teaching Junior Secondary?

**Example**:
```
Question: "How do I renew my membership?"
Answer: "Log into your dashboard, navigate to 'Subscriptions', and click 'Renew Membership'. Payment can be made via Paystack."
Order: 6
Is Active: ✅
```

---

### 5. **Partners Section**
**Admin Path**: `Core → Partners`

**Fields to Manage**:
- ✅ Partner name
- ✅ Logo image
- ✅ Website URL
- ✅ Display order
- ✅ Active/Inactive toggle

**Default Partners** (if CMS empty):
1. British Council
2. Edinburgh College, London
3. Africa ELTA
4. IATEFL

**Example**:
```
Name: "Cambridge Assessment English"
Logo: [Upload logo image - transparent PNG recommended]
Website: https://www.cambridgeenglish.org/
Order: 5
Is Active: ✅
```

**Design Notes**:
- Logos display in grayscale by default
- Turn to full color on hover
- Recommended size: 200x100px, transparent background

---

### 6. **Testimonials Section** (Optional)
**Admin Path**: `Core → Testimonials`

**Fields to Manage**:
- ✅ Name
- ✅ Role/Title
- ✅ Organization
- ✅ Testimonial text
- ✅ Photo (optional)
- ✅ Rating (1-5 stars)
- ✅ Display order
- ✅ Active/Inactive toggle

**Example**:
```
Name: "Dr. Adaeze Okonkwo"
Role: "English Department Head"
Organization: "Lagos State University"
Testimonial: "ELTAN has transformed how I approach teaching. The professional development opportunities are exceptional."
Photo: [Upload headshot]
Rating: 5
Order: 1
Is Active: ✅
```

---

### 7. **Site Settings** (Global)
**Admin Path**: `Core → Site Settings`

**Fields to Manage**:
- ✅ Site name
- ✅ Site description
- ✅ Contact email
- ✅ Contact phone
- ✅ Contact address
- ✅ Footer text
- ✅ Logo

**Used In**:
- Footer
- Meta tags
- Contact information

---

### 8. **Social Links**
**Admin Path**: `Core → Social Links`

**Fields to Manage**:
- ✅ Platform name (Facebook, Twitter, LinkedIn, Instagram)
- ✅ URL
- ✅ Display order
- ✅ Active/Inactive toggle

**Used In**:
- Footer social pills

---

## 📊 Automatic Database Content

These sections pull automatically from existing database models:

### **Upcoming Events**
**Source**: `Events` model
**Query**: Next 3 events with `event_date >= today`
**Displays**:
- Event title
- Event date (formatted)
- Location
- Link to event details

**No Admin Setup Required** - Just create events as normal

---

### **Active Conference**
**Source**: `EltanConference` model
**Query**: Active conference with `end_date >= today` and `is_active=True`
**Displays**:
- Featured badge
- Conference title
- Theme
- Start and end dates
- Venue
- "Register Now" button

**No Admin Setup Required** - Conference automatically appears when active

---

### **Latest News**
**Source**: `News` model
**Query**: Last 3 published articles (`is_published=True`)
**Displays**:
- Article headline
- Published date
- Excerpt
- Featured image
- Link to full article

**No Admin Setup Required** - News articles auto-appear when published

---

## 🎯 How to Add/Edit Content

### Step-by-Step: Adding a New Feature

1. **Login to Admin**
   - Go to: http://127.0.0.1:8000/admin
   - Email: onahjonah@gmail.com
   - Password: admin123

2. **Navigate to Features**
   - Click "Core" in left sidebar
   - Click "Features"

3. **Add Feature**
   - Click "Add Feature +" button (top right)

4. **Fill in Details**
   ```
   Title: "Research Publications"
   Description: "Access peer-reviewed research in English language teaching from our journal."
   Icon: article (or upload custom image)
   Link: /publications/
   Order: 8 (will appear 8th)
   Is Active: ✅
   ```

5. **Save**
   - Click "Save" or "Save and add another"

6. **View Changes**
   - Go to http://127.0.0.1:8000/
   - New feature appears immediately!

---

### Step-by-Step: Adding a Hero Slide

1. **Navigate**: Admin → Core → Hero Slides
2. **Add Slide**: Click "Add Hero Slide +"
3. **Upload Image**: Choose high-quality image (1920x1080px recommended)
4. **Add Text**:
   ```
   Title: "2025 Annual Conference"
   Subtitle: "Building Excellence in English Language Teaching"
   CTA Text: "Learn More"
   CTA Link: /conferences/1/
   Order: 1
   Is Active: ✅
   ```
5. **Save** → Slide appears in carousel!

---

### Step-by-Step: Updating Statistics

1. **Navigate**: Admin → Core → Statistics
2. **Click** on existing statistic (e.g., "Active Members")
3. **Update**:
   ```
   Number: 1,500+ (changed from 500+)
   Label: Registered Teachers (changed from Active Members)
   ```
4. **Save** → Updated immediately on homepage!

---

## 🔄 Content Fallback Strategy

The landing page uses a **smart fallback system**:

| Section | If CMS Has Data | If CMS Empty |
|---------|----------------|--------------|
| Hero Slides | Shows carousel | Shows static hero with default content |
| Statistics | Shows CMS stats | Shows 4 default stats |
| Features | Shows CMS features | Shows 6 ELTAN default features |
| FAQs | Shows CMS FAQs | Shows 5 default questions |
| Partners | Shows CMS partners | Shows 4 static partner logos |
| Testimonials | Shows carousel | Section hidden |
| Events | Shows from DB | Shows "No events" message |

**Benefits**:
- ✅ Page never looks empty
- ✅ Professional defaults aligned with ELTAN's mission
- ✅ Gradual CMS population possible
- ✅ No broken layouts

---

## 🎨 Material Icons Quick Reference

Common icons for ELTAN features:

| Icon Name | Use Case |
|-----------|----------|
| `event_available` | Conferences, workshops |
| `school` | Education, training |
| `library_books` | Resources, materials |
| `people` | Members, community |
| `diversity_3` | Special Interest Groups |
| `volunteer_activism` | Volunteer programs |
| `work` | Jobs, careers |
| `workspace_premium` | Certifications, awards |
| `local_library` | Research, publications |
| `support_agent` | Support, help |
| `groups` | Networking, collaboration |
| `military_tech` | Achievement, recognition |

**Full Icon Library**: https://fonts.google.com/icons

**How to Use**:
1. Browse icons on Google Fonts
2. Copy icon name (e.g., "book")
3. Paste into "Icon" field in admin
4. Icon appears with orange gradient background

---

## 📝 Content Guidelines

### Hero Slides
- **Title**: 5-10 words, action-oriented
- **Subtitle**: 15-25 words, clear value proposition
- **Image**: 1920x1080px, high quality, relevant to message
- **CTA**: Clear action verb (Register, Join, Learn, Explore)

### Statistics
- **Number**: Use "+" or "%" for impact (500+, 95%)
- **Label**: 1-3 words, specific (not generic)
- **Keep**: 4-6 stats total (not too many)

### Features
- **Title**: 2-5 words, benefit-focused
- **Description**: 20-40 words, specific value
- **Link**: Point to relevant internal page
- **Limit**: 6-9 features for best layout

### FAQs
- **Question**: Natural language, what users actually ask
- **Answer**: 30-100 words, actionable information
- **Order**: Most common questions first
- **Limit**: 5-8 FAQs for scannability

### Partners
- **Logo**: PNG with transparent background
- **Size**: 200x100px (maintains aspect ratio)
- **Quality**: High resolution for retina displays

---

## 🚀 Quick Customization Examples

### Change Hero Message
```
Admin → Core → Hero Slides → Edit first slide
Title: "Transform Your Teaching Career with ELTAN"
Subtitle: "Join 1,200+ English language educators nationwide"
Save
```

### Add New Statistic
```
Admin → Core → Statistics → Add Statistic +
Number: 25+
Label: Years of Excellence
Icon: star
Color: #E67918
Order: 5
Is Active: ✅
Save
```

### Update Feature Description
```
Admin → Core → Features → Click "PRELIM Resources"
Description: "Download FREE lesson plans, teaching aids, and assessment templates for Junior Secondary (JS1-JS3). Partnership with British Council and Edinburgh College."
Save
```

### Add Partner Logo
```
Admin → Core → Partners → Add Partner +
Name: "TESOL International"
Logo: [Upload logo.png]
Website: https://www.tesol.org
Order: 5
Is Active: ✅
Save
```

---

## 🔧 Advanced Customization

### Changing Section Order

Sections appear in this order (fixed in template):
1. Hero
2. Statistics
3. Features
4. About ELTAN
5. Professional Growth
6. Events & Conferences
7. Partners
8. Community Impact
9. FAQs
10. Call-to-Action
11. Footer

To reorder **items within sections**, use the "Order" field:
- Order: 1 = appears first
- Order: 2 = appears second
- etc.

### Hiding Sections

To hide optional sections:
- **Testimonials**: Don't add any testimonials in CMS
- **Partners**: Mark all partners as "Is Active: ❌"
- **Events**: Section shows "No events" if none upcoming

### Custom Colors

Statistics support custom colors:
```
Color: #E67918  (ELTAN orange)
Color: #1565C0  (ELTAN blue)
Color: #00796B  (ELTAN teal)
Color: #43A047  (Green for growth)
Color: #7B1FA2  (Purple for creativity)
```

---

## 📋 Content Checklist for New Admins

### Initial Setup (Recommended):

- [ ] Add 3-5 hero slides
- [ ] Update 4 statistics with current numbers
- [ ] Add 2-3 custom features (beyond defaults)
- [ ] Add 5-10 FAQs based on common questions
- [ ] Upload partner logos (if not already showing)
- [ ] Add 3-5 testimonials from members
- [ ] Update site settings (contact info)
- [ ] Add social media links
- [ ] Create upcoming events
- [ ] Publish latest news articles

### Maintenance (Monthly):

- [ ] Update statistics with current member count
- [ ] Add new events/conferences
- [ ] Publish new news articles
- [ ] Review and update FAQs
- [ ] Rotate hero slides for seasonal content
- [ ] Add new testimonials

### Seasonal (Yearly):

- [ ] Update conference hero slide
- [ ] Refresh partner logos
- [ ] Archive old events
- [ ] Update "About" content sections
- [ ] Review all features for relevance

---

## 🎓 Training Resources

### For Content Editors:
1. **Material Icons**: https://fonts.google.com/icons
2. **Image Optimization**: https://tinypng.com/
3. **Color Picker**: https://htmlcolorcodes.com/
4. **Markdown Guide**: https://www.markdownguide.org/

### For Administrators:
- Django Admin docs: https://docs.djangoproject.com/en/5.0/ref/contrib/admin/
- CKEditor formatting: Built into admin interface

---

## ❓ Common Questions

**Q: Why don't I see my changes?**
A: Make sure "Is Active" is checked ✅ and you've saved the form.

**Q: How many features should I add?**
A: 6-9 is optimal. Too many overwhelms users.

**Q: Can I use custom images instead of icons?**
A: Yes! Upload an image in the Feature's "Image" field instead of using an icon name.

**Q: What if I delete all CMS content?**
A: The page will show professional defaults - it never looks broken.

**Q: How do I reorder items?**
A: Use the "Order" field. Lower numbers appear first.

**Q: Can I add HTML to descriptions?**
A: Yes, most text fields support CKEditor rich text formatting.

**Q: What image sizes should I use?**
A:
- Hero slides: 1920x1080px
- Partner logos: 200x100px
- Feature images: 400x300px
- Testimonial photos: 200x200px (square)

---

## 🎯 Current Status

### ✅ Fully Dynamic Sections:
- Hero slider
- Statistics
- Features
- FAQs
- Partners
- Testimonials
- Events & Conferences (auto from DB)
- Latest News (auto from DB)

### 📝 Static Content Sections (Can be made dynamic):
- About ELTAN text
- Professional Growth text
- Community Impact text
- CTA section text

**Note**: These can be moved to CMS if needed using HomePage model fields.

---

## 🚀 Next Steps

1. **Populate CMS**: Add initial content through admin
2. **Test**: View homepage and verify all sections display correctly
3. **Train staff**: Share this guide with content managers
4. **Monitor**: Check analytics to see which sections get most engagement
5. **Iterate**: Update content based on user feedback

---

*Last Updated: October 24, 2025*
*Django Version: 5.0.4*
*Template: templates/landing/home_redesigned.html*
*View Function: membership/views.py:home_redesigned*
