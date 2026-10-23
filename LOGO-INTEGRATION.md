# Nyarugenge View logo assets

The source repository had no website files, so a simple GitHub Pages landing page now uses these assets. The header file is the complete supplied wordmark. Small browser and home-screen icons use the city-and-ruler mark so it remains recognizable at small sizes.

Add these tags to the document `<head>`:

```html
<link rel="icon" type="image/png" sizes="16x16" href="./public/images/favicon-16x16.png">
<link rel="icon" type="image/png" sizes="32x32" href="./public/images/favicon-32x32.png">
<link rel="icon" href="./public/images/favicon.ico" sizes="any">
<link rel="apple-touch-icon" sizes="180x180" href="./public/images/apple-touch-icon.png">
<link rel="manifest" href="./public/site.webmanifest">
<meta name="theme-color" content="#e6ddcd">
```

Use the complete logo in the site header:

```html
<a href="/" aria-label="Nyarugenge View home">
  <img src="./public/images/nyarugenge-view-logo.png" alt="Nyarugenge View"
       style="display:block;width:min(100%, 320px);height:auto">
</a>
```

Files: full wordmark PNG (794×758); favicon PNGs (16, 32, 48 px) and ICO (16/32 px); Apple touch icon (180×180); Android icons (192×192 and 512×512); web manifest.
