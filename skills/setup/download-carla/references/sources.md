# Where CARLA actually comes from

Detail layer for `download-carla`. Every URL, size and naming quirk below was
resolved live (2026-08) against the GitHub API and the CDN; `list`/`resolve` re-query
it, so treat the numbers as illustrative and the *mechanisms* as the contract.

## GitHub releases carry no assets

`GET /repos/carla-simulator/carla/releases` returns **zero attached assets** for
every release. The download links live in the release **body**, as markdown
pointing at `tiny.carla.org` shortlinks:

```
- `[Ubuntu]` [CARLA_0.9.16.tar.gz](https://tiny.carla.org/carla-0-9-16-linux)
- `[Ubuntu]` [AdditionalMaps_0.9.16.tar.gz](https://tiny.carla.org/additional-maps-0-9-16-linux)
- `[Windows]` [CARLA_0.9.16.zip](https://tiny.carla.org/carla-0-9-16-windows)
```

Those redirect (HTTP **308**) to `https://carla-releases.b-cdn.net/...`. Two
practical consequences:

- The skill parses the body and follows the redirect. It never trusts a
  constructed URL except as a last-resort fallback.
- `urllib`'s HEAD does **not** follow a 308 (it raises `HTTPError 308`), which is
  why size probing uses `curl -sIL`, falling back to a 1-byte ranged GET.

## Naming is not stable across the line

| Release | Resolved file | Size |
|---|---|---|
| 0.9.16 | `Linux/CARLA_0.9.16.tar.gz` | 8.3 GB |
| 0.9.16 maps | `Linux/AdditionalMaps_0.9.16.tar.gz` | 14.8 GB |
| 0.9.15 | `Linux/CARLA_0.9.15.tar.gz` | 8.4 GB |
| 0.9.16 (Windows) | `Windows/CARLA_0.9.16.zip` | 7.8 GB |
| **0.10.0** | `Linux/Carla-0.10.0-Linux-Shipping.tar.gz` | 10.4 GB |
| nightly | `Linux/Dev/CARLA_Latest.tar.gz` | 8.4 GB |

`Linux/CARLA_0.10.0.tar.gz` returns **404** — the UE5 line renamed the artifact.
Anything that builds URLs from a template breaks there, which is the whole reason
for reading the release body.

The 0.10 line also renames the launcher (`CarlaUnreal.sh`, not `CarlaUE4.sh`), so
`find_launcher` looks for both. Note that a 0.10 download is a **UE5** build: the
`ue4` skills do not apply to it, and its client wheel is likewise 0.10.x.

## What each mode gives you

### `release` / `nightly`

A cooked, runnable simulator. Contains:

- `CarlaUE4.sh` (or `CarlaUnreal.sh`) — the launcher `run-carla-server` detects;
- `PythonAPI/carla/dist/*.whl` — the **matching** client, which is why
  [[install-python-api]] prefers a bundled wheel over PyPI;
- `Import/` + `ImportAssets.sh` — where AdditionalMaps is staged and imported;
- cooked content only: **no source**, so nothing here can be built or edited.

`nightly` is the same shape with no version identity — it is a moving target, fine
for "does master fix my bug", wrong for anything reproducible.

### `git`

A source checkout, and *only* the source: **content is not included**. The maps
and assets are a separate ~31 GB fetch ([[build-carla-ue4]] step 05), and the
engine is another ~80 GB build. A checkout is the right choice only when the goal
is building, importing assets, or changing C++ — otherwise a release is two orders
of magnitude cheaper.

`--depth 1` is used deliberately: full CARLA history is large and no skill needs it.
Pass a tag (`--ref 0.9.16`) for a released source tree, or a branch (`ue4-dev`,
`ue5-dev`) for development.

### `docker`

`carlasim/carla:<tag>` ships the simulator, headless, and expects the NVIDIA
container runtime plus `--net=host` for the RPC/streaming ports. The client is not
in the image: install it on the host with [[install-python-api]]. Useful for CI and
for keeping a machine clean; not useful for the `ue4` build/import skills, which
need a real checkout on the filesystem.

## Disk arithmetic

The check in `check_env.sh` uses these numbers:

| Step | Cost |
|---|---|
| release archive | ~8.3 GB (0.9.x) / ~10.4 GB (0.10) |
| extraction | roughly the same again |
| **so a release needs** | **~19 GB free**, transiently |
| AdditionalMaps archive | ~14.8 GB, plus the import |
| a checkout + content + engine | ~1 GB + ~31 GB + ~80 GB |

The archive is deleted after a verified extraction (unless `--keep-archive`), so the
steady-state cost is roughly the extracted size.

## Integrity

CARLA publishes no checksums for these artifacts, so the strongest available check
is the CDN's `Content-Length` compared against the file on disk — which the skill
does before extracting, and which also makes a truncated resume detectable. There is
no signature to verify; if that matters for your environment, mirror the artifacts
yourself and check them out-of-band.
