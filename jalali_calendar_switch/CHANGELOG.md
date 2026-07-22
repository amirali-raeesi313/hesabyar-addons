# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-10-17

### Added
- Complete Jalali calendar integration for Odoo 18
- User toggle to switch between Gregorian and Jalali calendars
- Persian digits support and conversion
- Calendar view integration with FullCalendar
- Date picker integration
- User preference field for Jalali calendar
- Comprehensive test suite
- Full documentation in Persian and English
- Support for jalali-moment library for accurate date conversion

### Features
- **Calendar Integration**: Seamless integration with Odoo's calendar views
- **Date Conversion**: Accurate conversion between Gregorian and Jalali dates using jalali-moment
- **User Preferences**: Individual user settings for calendar preference
- **Persian Support**: Full support for Persian digits and date formatting
- **Toggle Functionality**: Easy switching between calendar systems
- **Responsive Design**: Works on all device sizes

### Technical Details
- **Backend**: Python models extending res.users
- **Frontend**: JavaScript modules using Odoo's module system
- **Dependencies**: jalali-moment, moment.js
- **Compatibility**: Odoo 18.x
- **License**: LGPL-3

### Installation
1. Copy the plugin to your Odoo addons directory
2. Restart Odoo service
3. Install the plugin from Apps menu
4. Configure user preferences to enable Jalali calendar

### Usage
1. Go to Settings > Users & Companies > Users
2. Edit your profile
3. Enable "Use Jalali Calendar" field
4. Calendar views will automatically show Jalali dates

### Files Structure
```
jalali_calendar_switch/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py
├── models/
│   ├── __init__.py
│   └── res_users.py
├── static/
│   └── src/
│       ├── js/
│       │   ├── moment.min.js
│       │   ├── jalali-moment.min.js
│       │   ├── jalaali_utils.js
│       │   ├── jalali_toggle.js
│       │   ├── jalali_date_patch.js
│       │   └── calendar_jalali_patch.js
│       └── xml/
│           └── jalali_templates.xml
├── views/
│   └── res_users_views.xml
└── tests/
    ├── __init__.py
    └── test_jalali_calendar.py
```

### Known Issues
- None reported in this version

### Future Plans
- Enhanced date picker integration
- Additional calendar views support
- Performance optimizations
- Extended Persian language support
