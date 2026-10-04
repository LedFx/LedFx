# Changelog

## [2.2.1](https://github.com/LedFx/LedFx/compare/v2.2.0...v2.2.1) (2026-10-04)


### Bug Fixes

* backport maintenance repairs for 2.2.1 ([74012f7](https://github.com/LedFx/LedFx/commit/74012f78f0caa3d8bfca9b85532709a61286f71f))

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
