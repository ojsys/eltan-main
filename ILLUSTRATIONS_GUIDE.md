# ELTAN Illustrations Integration Guide

## Free Illustration Libraries

We're using free, open-source illustration libraries that can be customized to match ELTAN's brand colors.

### Recommended Sources

#### 1. **unDraw** (Primary - Recommended)
- **Website**: https://undraw.co/illustrations
- **License**: Free for commercial and personal use
- **Customization**: Can change primary color to match ELTAN orange (#E67918)
- **Format**: SVG (scalable, perfect for web)

**How to Download:**
1. Visit https://undraw.co/illustrations
2. Search for keywords like: "leadership", "conference", "training", "community", "growth", "team"
3. Click on an illustration
4. Change the color to `#E67918` (ELTAN orange) using the color picker
5. Click "Download SVG"
6. Save to `/Users/Apple/projects/eltan2/static/illustrations/`

**Recommended Illustrations:**

| Purpose | Search Term | Suggested Filename |
|---------|-------------|-------------------|
| Hero Section | "team work", "office" | `leadership.svg` |
| Conferences | "presentation", "conference" | `conference.svg` |
| Training | "online learning", "teacher" | `training.svg` |
| Community | "community", "team" | `community.svg` |
| Growth | "growth", "charts" | `growth.svg` |
| Events | "calendar", "events" | `events.svg` |
| Resources | "file searching", "folder" | `resources.svg` |
| Profile | "profile", "user" | `profile.svg` |

#### 2. **Storyset by Freepik**
- **Website**: https://storyset.com/
- **License**: Free with attribution (or premium for no attribution)
- **Customization**: Full color customization, animated versions available
- **Format**: SVG, PNG, GIF (animated)

**How to Download:**
1. Visit https://storyset.com/
2. Browse categories: Business, Education, Technology
3. Select an illustration
4. Click "Customize"
5. Change colors to ELTAN palette:
   - Primary: #E67918
   - Secondary: #1565C0
   - Accent: #00796B
6. Download as SVG
7. Save to `/Users/Apple/projects/eltan2/static/illustrations/`

#### 3. **Humaaans** (For People Illustrations)
- **Website**: https://www.humaaans.com/
- **License**: Free for commercial use
- **Style**: Mix-and-match people illustrations
- **Format**: SVG

#### 4. **DrawKit**
- **Website**: https://www.drawkit.com/
- **License**: Free for personal and commercial use
- **Style**: Hand-drawn, modern
- **Format**: SVG, PNG

## Quick Setup Instructions

### Step 1: Create Illustrations Directory
```bash
mkdir -p /Users/Apple/projects/eltan2/static/illustrations
```

### Step 2: Download Essential Illustrations

Visit unDraw and download these (with color #E67918):

1. **Leadership/Hero** - Search "team work"
   - Save as: `leadership.svg`

2. **Conference** - Search "presentation"
   - Save as: `conference.svg`

3. **Training** - Search "online learning"
   - Save as: `training.svg`

4. **Community** - Search "community"
   - Save as: `community.svg`

5. **Growth/Stats** - Search "growth analytics"
   - Save as: `growth.svg`

6. **Events** - Search "events"
   - Save as: `events.svg`

7. **Resources** - Search "folder"
   - Save as: `resources.svg`

8. **Dashboard** - Search "dashboard"
   - Save as: `dashboard.svg`

### Step 3: Organize Files

Your directory structure should look like:
```
static/
├── illustrations/
│   ├── leadership.svg
│   ├── conference.svg
│   ├── training.svg
│   ├── community.svg
│   ├── growth.svg
│   ├── events.svg
│   ├── resources.svg
│   ├── dashboard.svg
│   ├── profile.svg
│   └── login.svg
├── images/
│   ├── logo.png
│   ├── favicon.png
│   └── partners/
│       ├── partner1.png
│       ├── partner2.png
│       └── partner3.png
```

## Alternative: Using Placeholder Images

If you want to get started quickly without downloading illustrations, you can use placeholder services:

### Option 1: Illustration Placeholders
```html
<!-- In your templates -->
<img src="https://via.placeholder.com/400x300/E67918/FFFFFF?text=Leadership" alt="Leadership">
```

### Option 2: SVG Placeholders with Icons
Create simple SVG illustrations with Material Icons:

```html
<svg width="400" height="300" viewBox="0 0 400 300">
    <rect width="400" height="300" fill="#FFDCC2"/>
    <text x="200" y="150" font-family="Material Symbols Outlined"
          font-size="100" fill="#E67918" text-anchor="middle">
        groups
    </text>
</svg>
```

## Color Customization

When customizing illustrations, use these ELTAN brand colors:

| Color Name | Hex Code | Usage |
|------------|----------|-------|
| Primary Orange | `#E67918` | Main brand color, primary elements |
| Secondary Blue | `#1565C0` | Secondary elements, accents |
| Tertiary Teal | `#00796B` | Additional accent color |
| Background Peach | `#FFDCC2` | Light backgrounds |
| Surface Blue | `#D1E4FF` | Card backgrounds |

## Implementation Example

In your templates:

```django
{% load static %}

<!-- Hero Illustration -->
<img src="{% static 'illustrations/leadership.svg' %}"
     alt="Leadership Illustration"
     style="width: 100%; max-width: 400px;">

<!-- Conference Feature -->
<img src="{% static 'illustrations/conference.svg' %}"
     alt="Professional Conferences"
     class="feature-illustration">
```

## Fallback Strategy

If illustrations aren't ready yet, the templates will still work with:

1. **Material Icons** - Already integrated
2. **Colored backgrounds** - Using brand colors
3. **Placeholder images** - Can be replaced later

## License Compliance

### unDraw
- ✅ Free for commercial use
- ✅ No attribution required
- ✅ Can modify colors

### Storyset
- ✅ Free with attribution
- Attribution text: `Illustration by <a href="https://storyset.com/">Storyset</a>`
- Can upgrade to remove attribution

### Best Practice
Add attribution in footer:
```html
<!-- Footer -->
<p class="text-sm text-muted">
    Illustrations by <a href="https://undraw.co">unDraw</a>
</p>
```

## Quick Start Commands

```bash
# 1. Create directory
mkdir -p static/illustrations

# 2. Download illustrations from unDraw
# Visit https://undraw.co/illustrations
# Change color to #E67918
# Download and save to static/illustrations/

# 3. Verify files
ls static/illustrations/

# 4. Update templates are already configured to use these files
```

## Need Help?

If you need specific illustrations:
1. Describe what you need (e.g., "professional conference setting")
2. Visit https://undraw.co/illustrations
3. Search for your description
4. Customize color to #E67918
5. Download and place in `static/illustrations/`

The templates are ready - just add the SVG files!
