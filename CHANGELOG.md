# Changelog

## [3.0.0](https://github.com/LedFx/LedFx/compare/v2.2.0...v3.0.0) (2026-10-04)


### ⚠ BREAKING CHANGES

* **api:** GET /api/effects/{effect_id} and POST /api/get_image now return 404.

### Features

* **api-v2:** generate, serve and check an OpenAPI 3.1 spec ([#2024](https://github.com/LedFx/LedFx/issues/2024)) ([877147a](https://github.com/LedFx/LedFx/commit/877147a6779ae939afb5aa87e67f9b887e87b6e6))
* **api-v2:** serve an offline API reference at /api/v2/docs ([#2027](https://github.com/LedFx/LedFx/issues/2027)) ([1d0f2de](https://github.com/LedFx/LedFx/commit/1d0f2de2fa4a1c1acf94f36634b90805cf5ebe61))
* **api-v2:** serve typed /api/v2 routes with Problem errors ([#2023](https://github.com/LedFx/LedFx/issues/2023)) ([e881b4f](https://github.com/LedFx/LedFx/commit/e881b4f0aa1a1121c106726e1aae1c00e60d540f))
* **api-v2:** serve virtuals through a shared manager ([#2042](https://github.com/LedFx/LedFx/issues/2042)) ([cde9ebd](https://github.com/LedFx/LedFx/commit/cde9ebd6cab97eeba7f129ad7d84ee49aa9bbebf))
* **api:** lay the API v2 foundations ([#2022](https://github.com/LedFx/LedFx/issues/2022)) ([4afc21f](https://github.com/LedFx/LedFx/commit/4afc21f01fb2e9b67fe7078ff5ca9c78ba647cdd))
* **config:** add a versioned, crash-safe ConfigStore ([#1977](https://github.com/LedFx/LedFx/issues/1977)) ([dcd2fc7](https://github.com/LedFx/LedFx/commit/dcd2fc7444c322cc190b5e2d0b6b099eecaa2d02))
* **config:** typed core config with lenient loading ([#1979](https://github.com/LedFx/LedFx/issues/1979)) ([b029f3f](https://github.com/LedFx/LedFx/commit/b029f3f56f90126ed5ae0abb0055b38fbca3e30d))
* **config:** typed field types and JSON Schema export ([#1978](https://github.com/LedFx/LedFx/issues/1978)) ([c34a536](https://github.com/LedFx/LedFx/commit/c34a53635337b32b4b0162552b8ad86cb0876704))
* **config:** validate plugin configs with pydantic models ([#1980](https://github.com/LedFx/LedFx/issues/1980)) ([cb7035e](https://github.com/LedFx/LedFx/commit/cb7035e6c9369ae896d5ded3d9859ac1401b4317))


### Bug Fixes

* aoisendspin to unpaired mode ([#2063](https://github.com/LedFx/LedFx/issues/2063)) ([7818f11](https://github.com/LedFx/LedFx/commit/7818f114709335117590e9746a143482314865cd))
* **api:** answer bad input with a validation error or a clear reason ([#1986](https://github.com/LedFx/LedFx/issues/1986)) ([918a941](https://github.com/LedFx/LedFx/commit/918a9415acb5b5396c1905aeeff317dffd0dc3d0))
* **api:** built-in presets and colors are read-only; no false success ([#1993](https://github.com/LedFx/LedFx/issues/1993)) ([1831308](https://github.com/LedFx/LedFx/commit/1831308dfe8f25b075f80070a55aa0e0df5d317b))
* **api:** keep blocking network calls off the event loop ([#1996](https://github.com/LedFx/LedFx/issues/1996)) ([ef12500](https://github.com/LedFx/LedFx/commit/ef1250037f45ff6a4e71a42649eaa36c7daa7217))
* **api:** remove two broken v1 routes; correct the v1 docs ([#1998](https://github.com/LedFx/LedFx/issues/1998)) ([4ffceb0](https://github.com/LedFx/LedFx/commit/4ffceb0562a87f4ad149ca1ebdb028e5eba8cd18))
* **api:** route scenes, presets and Home Assistant through the virtuals manager ([#2055](https://github.com/LedFx/LedFx/issues/2055)) ([30f00c0](https://github.com/LedFx/LedFx/commit/30f00c057c444a47074caf62598e881ce0a7c407))
* **api:** schedule power stops and delayed scene activations, with caps ([#1995](https://github.com/LedFx/LedFx/issues/1995)) ([ae4333e](https://github.com/LedFx/LedFx/commit/ae4333ee7c5ce29d7d1c5c61925886cc30ffedd7))
* **api:** small v1 fixes: device not-found message, one PlaylistManager ([#1992](https://github.com/LedFx/LedFx/issues/1992)) ([5e4650e](https://github.com/LedFx/LedFx/commit/5e4650e8d0597db20af32746da28f3c67ac7b664))
* **api:** Spotify trigger edit, integration names, active state on update ([#1997](https://github.com/LedFx/LedFx/issues/1997)) ([4077a06](https://github.com/LedFx/LedFx/commit/4077a060244be5850e2021c0875d47d1c8ea3499))
* **api:** virtual tools run only what they implement, with validated input ([#1994](https://github.com/LedFx/LedFx/issues/1994)) ([84e8716](https://github.com/LedFx/LedFx/commit/84e8716ba781564bd5a03ba3bfd365ea371e3409))
* **cache:** keep image analysis outside the image cache lock ([8066452](https://github.com/LedFx/LedFx/commit/8066452bf1c7989f8880b15311eb8ccf2e4a8b58))
* **color:** treat a hex color too long for RGB as an invalid color ([8066452](https://github.com/LedFx/LedFx/commit/8066452bf1c7989f8880b15311eb8ccf2e4a8b58))
* **e131:** let each sACN sender use its own source port ([#2015](https://github.com/LedFx/LedFx/issues/2015)) ([76b685e](https://github.com/LedFx/LedFx/commit/76b685e17fd0025b03ba2153732e19aad29ed7ed))
* harden device lifecycle and render loop; remove no-op dev auto-reload ([#1973](https://github.com/LedFx/LedFx/issues/1973)) ([bd744c2](https://github.com/LedFx/LedFx/commit/bd744c295268d56ee8abf9be807e6f8c1013c842))
* **installer:** close a running LedFx before upgrading and harden the installer ([#2020](https://github.com/LedFx/LedFx/issues/2020)) ([0bad737](https://github.com/LedFx/LedFx/commit/0bad737252025e7f7be0ceac6541f6fcf295e2f3))
* keep devices and transitions working after a pixel count change ([#2017](https://github.com/LedFx/LedFx/issues/2017)) ([24b8156](https://github.com/LedFx/LedFx/commit/24b815604d802cb239f66253ef3aa514b64cc326))
* **mdns:** close the zeroconf instance after each device scan ([#2016](https://github.com/LedFx/LedFx/issues/2016)) ([fa443e2](https://github.com/LedFx/LedFx/commit/fa443e23a14028f0e3615396530355270e1f2e54))
* **mqtt_hass:** publish the colour of the effect that changed ([#2013](https://github.com/LedFx/LedFx/issues/2013)) ([ddff497](https://github.com/LedFx/LedFx/commit/ddff49772409f01155e338d0d74a8f2632ae0b58))
* **qlc:** reconnect reliably and close the websocket session ([#2010](https://github.com/LedFx/LedFx/issues/2010)) ([ab3d5cb](https://github.com/LedFx/LedFx/commit/ab3d5cb1a1850e117c9029de6ceea879dc3f376c))
* resolve fourteen more runtime bugs exposed by strict typing ([#1972](https://github.com/LedFx/LedFx/issues/1972)) ([ec6ffc3](https://github.com/LedFx/LedFx/commit/ec6ffc382a4e74dd299d9181984ab68af7ded78c))
* resolve Sendspin typing and client API errors ([#1970](https://github.com/LedFx/LedFx/issues/1970)) ([8040be7](https://github.com/LedFx/LedFx/commit/8040be73553c6ebc64442f6c37ca870005ffdf7b))
* resolve ten runtime bugs exposed by strict typing ([#1971](https://github.com/LedFx/LedFx/issues/1971)) ([018f83c](https://github.com/LedFx/LedFx/commit/018f83c8a3427ffb2d9b448b058c13c981cc1904))
* stop expected conditions reaching Sentry as errors ([#2011](https://github.com/LedFx/LedFx/issues/2011)) ([c6a6087](https://github.com/LedFx/LedFx/commit/c6a6087c2912f818ed5b9ab63f868770a8cb899a))
* **virtuals:** clear an effect that is no longer registered ([#2018](https://github.com/LedFx/LedFx/issues/2018)) ([cab09be](https://github.com/LedFx/LedFx/commit/cab09be9770490093bc647bda7cfa0ccbe87fef3))
* **virtuals:** keep the original error when the effect fails again on rollback ([8066452](https://github.com/LedFx/LedFx/commit/8066452bf1c7989f8880b15311eb8ccf2e4a8b58))
* **websocket:** accept the frontend's Web Audio sample list ([#2014](https://github.com/LedFx/LedFx/issues/2014)) ([e0b240b](https://github.com/LedFx/LedFx/commit/e0b240b75f567a1080535fa7383abde901511f70))
* **websocket:** block virtual_update subscriptions ([#2012](https://github.com/LedFx/LedFx/issues/2012)) ([ae6870b](https://github.com/LedFx/LedFx/commit/ae6870ba247b00a3f99f2e7dd38961ffd5c16644))


### Documentation

* **cache:** describe what an image refresh actually does ([8066452](https://github.com/LedFx/LedFx/commit/8066452bf1c7989f8880b15311eb8ccf2e4a8b58))

## [2.2.0](https://github.com/LedFx/LedFx/compare/v2.1.9...v2.2.0) (2026-10-01)


### Features

* Add filtered boolean to equalizer2d effect ([#1836](https://github.com/LedFx/LedFx/issues/1836)) ([71bd8e8](https://github.com/LedFx/LedFx/commit/71bd8e8de56e0707f8073f3bb5c8f582edc5d38d))
* Add linux now-playing support ([#1835](https://github.com/LedFx/LedFx/issues/1835)) ([566de0f](https://github.com/LedFx/LedFx/commit/566de0fb6d32231022d7efa7684298f3af615792))
* Add melbank flag ([#1851](https://github.com/LedFx/LedFx/issues/1851)) ([83d7c99](https://github.com/LedFx/LedFx/commit/83d7c99a0172ae9afac80e9eb842532acac0208f))
* now_playing ([#1805](https://github.com/LedFx/LedFx/issues/1805)) ([c063949](https://github.com/LedFx/LedFx/commit/c063949968c0524e8a0caf00a96a4c9a424f9847))
* support Python 3.11–3.14 (drop 3.10, switch to pyfastnoiselite-ledfx) ([#1916](https://github.com/LedFx/LedFx/issues/1916)) ([ebf36fb](https://github.com/LedFx/LedFx/commit/ebf36fb4ee51d143270ddffd883e248b49e1bd62))


### Bug Fixes

* **audio:** preserve audio selection and reconnect Sendspin after Music Assistant restarts ([#1833](https://github.com/LedFx/LedFx/issues/1833)) ([284ec23](https://github.com/LedFx/LedFx/commit/284ec23465d476345bee92edf2f0910595c751bd))
* **audio:** preserve selected device on partial config updates ([#1831](https://github.com/LedFx/LedFx/issues/1831)) ([375209d](https://github.com/LedFx/LedFx/commit/375209dfa883150cb971bd3a4756ecfe47ad5490))
* Clean up Sendspin eager start and handle pause ([#1837](https://github.com/LedFx/LedFx/issues/1837)) ([091b723](https://github.com/LedFx/LedFx/commit/091b72396bf71e151a552e416df98be28d71d784))
* default gradient to off in now playing service config ([#1832](https://github.com/LedFx/LedFx/issues/1832)) ([1f7ed3a](https://github.com/LedFx/LedFx/commit/1f7ed3acb138bee0ae0af7df4579610502528064))
* **deps:** keep cryptography 48 on Intel macOS ([#1920](https://github.com/LedFx/LedFx/issues/1920)) ([b18344f](https://github.com/LedFx/LedFx/commit/b18344f36cf3afd83d921722a572ef96e27ddc3b))
* **deps:** update dependency aiosendspin to v9 ([#1913](https://github.com/LedFx/LedFx/issues/1913)) ([5bd35d7](https://github.com/LedFx/LedFx/commit/5bd35d7cd5d73c652e934b141ece29aed1d929e0))
* **deps:** update dependency mss to ~=10.2.0 ([#1899](https://github.com/LedFx/LedFx/issues/1899)) ([0ef565a](https://github.com/LedFx/LedFx/commit/0ef565a2c0a5ec6ee74719330d8ee94e52be740c))
* **deps:** update dependency pybase64 to ~=1.5.0 ([#1900](https://github.com/LedFx/LedFx/issues/1900)) ([f8a9108](https://github.com/LedFx/LedFx/commit/f8a9108e26609a28a6c711d1ac2f895d9cd64376))
* gap- device trap corner cases ([#1822](https://github.com/LedFx/LedFx/issues/1822)) ([e92bbac](https://github.com/LedFx/LedFx/commit/e92bbac609988c27f25e01cf77c6bfef0cb8ebfa))
* MacOS tray icon thread requirements ([#1860](https://github.com/LedFx/LedFx/issues/1860)) ([4c3858d](https://github.com/LedFx/LedFx/commit/4c3858d49f728b801d65317ce763afb95070c649))
* melt_and_sparkle suddenly changing. ([#1847](https://github.com/LedFx/LedFx/issues/1847)) ([d2d3c57](https://github.com/LedFx/LedFx/commit/d2d3c57f9ff9f97763eb80b15556e91da307bf3a))
* moved launchpad pro mk3 before pad pro [#1824](https://github.com/LedFx/LedFx/issues/1824) ([#1829](https://github.com/LedFx/LedFx/issues/1829)) ([cb9fc7c](https://github.com/LedFx/LedFx/commit/cb9fc7cd1809ed662a78db1d07a6352e5dc83dcb))
* **nanoleaf:** support Nanoleaf Essentials devices that report a length instead of a panel layout ([#1853](https://github.com/LedFx/LedFx/issues/1853)) ([a7e44a5](https://github.com/LedFx/LedFx/commit/a7e44a5f8eb38fd9036806f86a283aa9874df079))
* query the autofix workflow by filename, not name ([#1959](https://github.com/LedFx/LedFx/issues/1959)) ([7b5ea30](https://github.com/LedFx/LedFx/commit/7b5ea304b70ea97e90c18c2529700896360ad0ee))
* **security:** cap the frame count and total pixels of animated images so oversized GIFs cannot exhaust memory and CPU (GHSA-cjr3-wgv6-rq28) ([a7e44a5](https://github.com/LedFx/LedFx/commit/a7e44a5f8eb38fd9036806f86a283aa9874df079))
* **security:** check the request Origin and Host and build CORS headers from one policy; clients that reach LedFx by a non-local DNS name need it in allowed_hosts (GHSA-q86q-8gw9-jjgq) ([a7e44a5](https://github.com/LedFx/LedFx/commit/a7e44a5f8eb38fd9036806f86a283aa9874df079))
* **security:** close SSRF guard bypasses via IPv6 transition addresses, redirects and DNS rebinding (GHSA-pc6c-8c73-p6p2) ([a7e44a5](https://github.com/LedFx/LedFx/commit/a7e44a5f8eb38fd9036806f86a283aa9874df079))
* **security:** validate the Nanoleaf pairing address so requests cannot target arbitrary hosts and paths (GHSA-cc93-3vjc-976h) ([a7e44a5](https://github.com/LedFx/LedFx/commit/a7e44a5f8eb38fd9036806f86a283aa9874df079))


### Documentation

* explicitly define supported Python range (3.10–3.13) across install/build guides ([#1827](https://github.com/LedFx/LedFx/issues/1827)) ([6ceecbb](https://github.com/LedFx/LedFx/commit/6ceecbb2bbec8def99012f8feba34f9577adbe95))
* MusicBrainz Album Art and general dev notes shuffle ([#1818](https://github.com/LedFx/LedFx/issues/1818)) ([eecc25e](https://github.com/LedFx/LedFx/commit/eecc25e66e078dbc0d5d65fa87fbb0ec5e7f0b5a))
* prek commands that work on a fresh checkout; defer the blame entry ([53998aa](https://github.com/LedFx/LedFx/commit/53998aafa1acb9983117551e50d6526cf03b9e55))
* **sendspin:** document which Sendspin and Music Assistant versions work together ([#1848](https://github.com/LedFx/LedFx/issues/1848)) ([a7e44a5](https://github.com/LedFx/LedFx/commit/a7e44a5f8eb38fd9036806f86a283aa9874df079))

## Changelog

All notable changes to LedFx are documented here. This file started with the
release-please adoption (see the release PRs for history before that point);
newest entries are at the top.
