# ZGX AI Bridge - Lessons Learned

## Extension testing (2026-05-12)
- Onshape CSP does NOT block fetch() from Chrome extension content scripts to localhost/LAN IPs
- DOM injection via content script works cleanly, widget renders over the 3D viewport
- Context scraping captured: documentName, documentId, pageType, tabInfo (all workspace tabs)
- Feature tree class names did NOT match initial guesses (featureTree came back empty)
- Need to inspect Onshape DOM for actual feature tree selectors
- Zip packaging created nested folder - users need to point at the inner directory containing manifest.json
