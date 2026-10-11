"""Optional EnMAP investigation support. No imagery is bundled or fabricated.

Use through notebooks 03 and 04. Provider authentication and live raster reads have not
been exercised in the author's restricted workspace; numerical checks are local.
"""
from pathlib import Path
import json
import math
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
import numpy as np
import pandas as pd

CATALOG = 'https://geoservice.dlr.de/eoc/ogc/stac/v1'
COLLECTION = 'ENMAP_HSI_L2A'
BBOX = [31.41, 30.56, 31.46, 30.60]
MASKS = ['quality_classes', 'quality_cloud', 'quality_cloud_shadow',
         'quality_haze', 'quality_cirrus', 'quality_snow', 'quality_testflags']
REQUIRED = ['image', 'defective_pixel_mask'] + MASKS


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def status(out, state, **details):
    result = dict(state=state, updated_utc=datetime.now(timezone.utc).isoformat(),
                  hyperspectral_pixels_processed=False, **details)
    write_json(Path(out) / 'hyperspectral_status.json', result)
    return result


def trusted_url(url, host):
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname != host or p.username or p.password:
        raise ValueError('Unexpected provider URL; no credentials were sent.')
    return url


def item_date(item):
    p = item['properties']
    return str(p.get('datetime') or p.get('start_datetime') or '')


def catalogue_search(out, end_date='2026-10-04'):
    """Public metadata only. Exhaust pagination or report failure, never fake zero."""
    import requests
    from shapely.geometry import shape, box
    from rasterio.warp import transform_geom
    out = Path(out)
    status(out, 'searching', query_bbox=BBOX, search_end_date=end_date)
    params = dict(bbox=','.join(map(str, BBOX)), limit=100,
                  datetime=f'2022-04-27T00:00:00Z/{end_date}T23:59:59Z',
                  f='application/geo+json')
    url = f'{CATALOG}/collections/{COLLECTION}/items'
    items, seen_pages = {}, set()
    try:
        for page_number in range(50):
            trusted_url(url, 'geoservice.dlr.de')
            response = requests.get(url, params=params, timeout=(20, 90))
            response.raise_for_status()
            page = response.json()
            if page.get('type') != 'FeatureCollection' or 'features' not in page:
                raise ValueError('The provider did not return a STAC FeatureCollection.')
            for item in page['features']:
                if item.get('collection') != COLLECTION:
                    raise ValueError('Unexpected collection in catalogue result.')
                items[item['id']] = item
            next_link = next((x for x in page.get('links', []) if x.get('rel') == 'next'), None)
            if not next_link:
                break
            if next_link.get('method', 'GET') != 'GET':
                raise ValueError('Unsupported pagination method; results are incomplete.')
            url = urljoin(response.url, next_link['href'])
            params = None
            if url in seen_pages:
                raise ValueError('Repeated catalogue page; results are incomplete.')
            seen_pages.add(url)
        else:
            raise ValueError('Catalogue page limit reached; results are incomplete.')
        aoi = box(*BBOX)
        area = shape(transform_geom('EPSG:4326', 'EPSG:32636', aoi.__geo_interface__)).area
        records, kept = [], {}
        for item in items.values():
            footprint = shape(item['geometry'])
            overlap = footprint.intersection(aoi)
            if overlap.is_empty:
                continue
            fraction = shape(transform_geom('EPSG:4326', 'EPSG:32636', overlap.__geo_interface__)).area / area
            p, date = item['properties'], item_date(item)
            cloud = p.get('eo:cloud_cover')
            try:
                cloud = float(cloud)
            except (TypeError, ValueError):
                cloud = 100.0
            quality = p.get('enmap:overallQuality')
            suitable = (fraction >= .90 and 0 <= cloud <= 30 and str(quality) == '0'
                        and all(k in item.get('assets', {}) for k in REQUIRED) and bool(date))
            records.append(dict(scene_id=item['id'], acquisition_utc=date,
                                aoi_footprint_fraction=round(min(fraction, 1), 4),
                                scene_cloud_percent=cloud, overall_quality=quality,
                                within_2023_2024=date[:4] in ['2023', '2024'],
                                candidate_for_download=bool(suitable)))
            kept[item['id']] = item
        table = pd.DataFrame(records, columns=['scene_id', 'acquisition_utc', 'aoi_footprint_fraction',
                            'scene_cloud_percent', 'overall_quality', 'within_2023_2024',
                            'candidate_for_download'])
        if not table.empty:
            table = table.sort_values(['candidate_for_download', 'within_2023_2024',
                                      'scene_cloud_percent', 'acquisition_utc'],
                                     ascending=[False, False, True, False]).reset_index(drop=True)
        table.to_csv(out / 'coverage_candidates.csv', index=False)
        write_json(out / 'coverage_items.json', dict(type='FeatureCollection', features=list(kept.values())))
        candidates = table.loc[table.candidate_for_download == True]
        if candidates.empty:
            status(out, 'no_suitable_candidate', query_bbox=BBOX, search_end_date=end_date,
                   intersecting_scenes=len(table), search_complete=True,
                   explanation='No returned scene met this notebook\'s footprint, quality, cloud and asset rules. '
                               'This is not proof that EnMAP has never observed the area.')
            return table, None
        selected = kept[candidates.iloc[0].scene_id]
        write_json(out / 'selected_item.json', selected)
        status(out, 'candidate_found_not_downloaded', scene_id=selected['id'],
               acquisition_utc=item_date(selected), search_complete=True, query_bbox=BBOX,
               selection='Prefer 2023/2024; then lower scene cloud; then latest date. '
                         'Footprint >=90%, nominal quality, required assets present.')
        return table, selected
    except Exception as exc:
        status(out, 'search_failed', search_complete=False, query_bbox=BBOX,
               error_type=type(exc).__name__, explanation='Coverage is unknown. Run the search in Colab; '
               'a network error is not an empty catalogue result.')
        raise RuntimeError('EnMAP coverage search failed. Coverage remains unknown; keep the Sentinel results.') from None


def spectral_metadata(item):
    """Read actual per-band wavelengths/calibration; no hard-coded band numbers."""
    bands = item['assets']['image'].get('eo:bands')
    if not bands:
        raise ValueError('Expected EnMAP eo:bands metadata is missing. Do not guess calibration.')
    rows = []
    for i, b in enumerate(bands):
        # DLR uses nanometres in this collection. Accept conventional STAC micrometres too.
        wavelength = b.get('center_wavelength', b.get('eo:center_wavelength'))
        if wavelength is None:
            raise ValueError('A band has no wavelength.')
        nm = float(wavelength)
        if 0.3 < nm < 3:
            nm *= 1000
        gain, offset = b.get('enmap:gain_of_band'), b.get('enmap:offset_of_band')
        if gain is None or offset is None:
            raise ValueError('EnMAP band gain/offset is missing. Update the reader from provider metadata.')
        rows.append((i+1, nm, float(gain), float(offset)))
    metadata = np.asarray(rows, dtype=float)
    if not np.isfinite(metadata).all() or np.any(metadata[:, 2] <= 0):
        raise ValueError('Invalid spectral calibration metadata.')
    selected = metadata[(metadata[:, 1] >= 650) & (metadata[:, 1] <= 850)]
    selected = selected[np.argsort(selected[:, 1])]
    wavelengths = selected[:, 1]
    if len(wavelengths) < 20 or np.any(np.diff(wavelengths) <= 0) or np.max(np.diff(wavelengths)) > 12:
        raise ValueError('A sufficiently dense 650–850 nm spectrum is unavailable.')
    return selected


def fetch_clip(root, item, username, password):
    """Read a small native-grid window using a legitimate DLR Basic-auth account."""
    import rasterio
    from rasterio.windows import Window, from_bounds
    from rasterio.warp import transform_bounds, reproject, Resampling
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom
    from shapely.geometry import box
    root = Path(root)
    metadata = spectral_metadata(item)
    indices = metadata[:, 0].astype(int).tolist()
    assets = item['assets']
    for key in REQUIRED:
        trusted_url(assets[key]['href'], 'download.geoservice.dlr.de')
    options = dict(GDAL_HTTP_AUTH='BASIC', GDAL_HTTP_USERPWD=username + ':' + password,
                   GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', GDAL_HTTP_TIMEOUT='90',
                   GDAL_HTTP_MAX_RETRY='2', GDAL_HTTP_RETRY_DELAY='2', CPL_CURL_VERBOSE=False)
    # Credentials are scoped to this operation; neither written nor included in outputs.
    with rasterio.Env(**options):
        with rasterio.open(assets['image']['href']) as src:
            if src.crs is None or not src.crs.is_projected:
                raise ValueError('Expected a georeferenced projected L2A image.')
            if src.count != len(assets['image']['eo:bands']):
                raise ValueError('Raster bands and calibration metadata disagree.')
            if not (20 <= abs(src.res[0]) <= 40 and 20 <= abs(src.res[1]) <= 40):
                raise ValueError('Unexpected native spatial resolution.')
            bounds = transform_bounds('EPSG:4326', src.crs, *BBOX, densify_pts=21)
            w = from_bounds(*bounds, src.transform)
            c0, r0 = max(0, math.floor(w.col_off)), max(0, math.floor(w.row_off))
            c1, r1 = min(src.width, math.ceil(w.col_off+w.width)), min(src.height, math.ceil(w.row_off+w.height))
            if c1 <= c0 or r1 <= r0:
                raise ValueError('Raster does not overlap Zankalon.')
            window = Window(c0, r0, c1-c0, r1-r0)
            if window.width * window.height > 100000:
                raise ValueError('Unexpectedly large crop; refusing a full-scene read.')
            transform, crs = src.window_transform(window), src.crs
            raw = src.read(indices, window=window, masked=True).astype('float32').filled(np.nan)
            native_count = src.count
        calibrated = raw * metadata[:, 2, None, None] + metadata[:, 3, None, None]
        calibrated[~np.isfinite(calibrated) | (calibrated < 0)] = np.nan
        shape_2d = raw.shape[1:]

        def aligned(key, band_indexes):
            with rasterio.open(assets[key]['href']) as qa:
                result = np.full((len(band_indexes), *shape_2d), 255, dtype='uint8')
                for j, band in enumerate(band_indexes):
                    # Read a native QA window, then nearest-neighbour alignment, never bilinear flags.
                    q_bounds = transform_bounds(crs, qa.crs,
                        *rasterio.windows.bounds(window, src_transform), densify_pts=21)
                    request = from_bounds(*q_bounds, qa.transform)
                    qc, qr = math.floor(request.col_off), math.floor(request.row_off)
                    qw = Window(qc, qr, math.ceil(request.col_off+request.width)-qc,
                                math.ceil(request.row_off+request.height)-qr)
                    values = qa.read(band, window=qw, boundless=True, fill_value=255)
                    reproject(values, result[j], src_transform=qa.window_transform(qw), src_crs=qa.crs,
                              dst_transform=transform, dst_crs=crs, src_nodata=255,
                              dst_nodata=255, resampling=Resampling.nearest)
                return result

        # Retain source transform separately; no open image handle is needed below.
        src_transform = transform * rasterio.Affine.translation(-window.col_off, -window.row_off)
        aoi_native = transform_geom('EPSG:4326', crs, box(*BBOX).__geo_interface__)
        valid = geometry_mask([aoi_native], out_shape=shape_2d, transform=transform, invert=True)
        valid &= aligned('quality_classes', [1])[0] == 1
        for key in MASKS[1:]:
            valid &= aligned(key, [1])[0] == 0
        with rasterio.open(assets['defective_pixel_mask']['href']) as mask:
            if mask.count != native_count:
                raise ValueError('Unexpected defective-pixel mask layout; refuse to guess band mapping.')
        defects = aligned('defective_pixel_mask', indices)
        valid &= np.all(defects == 0, axis=0) & np.all(np.isfinite(calibrated), axis=0)
    crop = np.zeros(shape_2d, dtype='uint8')
    with rasterio.open(root / 'data/sample_input/zankalon_reference_crop_mask.tif') as src:
        reproject(rasterio.band(src, 1), crop, src_transform=src.transform, src_crs=src.crs,
                  dst_transform=transform, dst_crs=crs, dst_nodata=0, resampling=Resampling.nearest)
    crop = crop == 1
    valid &= crop
    calibrated[:, ~valid] = np.nan
    if not valid.any():
        raise ValueError('The clip has no crop-reference pixels passing all quality masks.')
    work = root / 'work/hyperspectral'
    work.mkdir(parents=True, exist_ok=True)
    cache = work / (hashlib.sha256(item['id'].encode()).hexdigest()[:16] + '_clip_private.npz')
    np.savez_compressed(cache, reflectance=calibrated.astype('float32'), valid=valid,
                        crop=crop, wavelengths_nm=metadata[:, 1],
                        transform=np.asarray(transform)[:6], crs=str(crs), scene_id=item['id'])
    return cache


def red_edge_metrics(wavelengths, spectra):
    """Descriptive spectral shape, not calibrated chlorophyll or salinity."""
    wavelengths, spectra = np.asarray(wavelengths), np.asarray(spectra)
    if spectra.ndim == 1:
        spectra = spectra[None, :]
    red, nir = [int(np.argmin(abs(wavelengths-nm))) for nm in (670, 800)]
    if abs(wavelengths[red]-670) > 10 or abs(wavelengths[nir]-800) > 10:
        raise ValueError('Required red/NIR wavelengths are missing.')
    ndvi = (spectra[:, nir]-spectra[:, red]) / (spectra[:, nir]+spectra[:, red]+1e-12)
    smooth = (spectra[:, :-2]+spectra[:, 1:-1]+spectra[:, 2:])/3
    mid = wavelengths[1:-1]
    gradient = np.gradient(smooth, mid, axis=1)
    keep = np.flatnonzero((mid >= 690) & (mid <= 750))
    if len(keep) < 5:
        raise ValueError('Too few red-edge bands.')
    maximum = np.argmax(gradient[:, keep], axis=1)
    position = mid[keep[maximum]].astype(float)
    slope = gradient[np.arange(len(spectra)), keep[maximum]]
    # A maximum at the range boundary or weak vegetation is not a reliable estimate.
    bad = ((maximum == 0) | (maximum == len(keep)-1) | (ndvi < .30)
           | (slope <= 0) | ~np.isfinite(spectra).all(axis=1))
    position[bad] = np.nan
    slope[bad] = np.nan
    return ndvi, position, slope


def analyse_clip(root, item, cache):
    import rasterio
    from rasterio.features import rasterize
    from rasterio.warp import transform_geom
    import matplotlib.pyplot as plt
    root = Path(root)
    out = root / 'results/hyperspectral'
    data = np.load(cache, allow_pickle=False)
    if str(data['scene_id']) != item['id']:
        raise ValueError('Cached pixels belong to a different scene.')
    cube, wl, valid, crop = [data[k] for k in ['reflectance', 'wavelengths_nm', 'valid', 'crop']]
    if (cube.ndim != 3 or cube.shape[0] != len(wl) or cube.shape[1:] != valid.shape
            or valid.shape != crop.shape or valid.size > 100000 or len(wl) < 20
            or not np.isfinite(wl).all() or np.any(np.diff(wl) <= 0)):
        raise ValueError('Unexpected cached clip shape or wavelengths; do not analyse it.')
    if valid.dtype != np.bool_ or crop.dtype != np.bool_:
        raise ValueError('Cached quality masks must be boolean arrays.')
    transform, crs = rasterio.Affine(*data['transform']), str(data['crs'])
    red, nir = [int(np.argmin(abs(wl-nm))) for nm in (670, 800)]
    pixel_ndvi = (cube[nir]-cube[red]) / (cube[nir]+cube[red]+1e-12)
    vegetation = valid & (pixel_ndvi >= .30)
    grid = json.loads((root / 'data/sample_input/zankalon_analysis_grid.geojson').read_text())
    cells = [f['properties']['cell_id'] for f in grid['features']]
    shapes = [(transform_geom('EPSG:4326', crs, f['geometry']), i+1)
              for i, f in enumerate(grid['features'])]
    labels = rasterize(shapes, out_shape=valid.shape, transform=transform,
                       fill=0, dtype='int32', all_touched=False)
    baseline = pd.read_csv(root / 'results/cell_comparison_summary.csv').set_index('cell_id')
    rows, spectra = [], []
    for i, cell in enumerate(cells):
        inside = labels == i+1
        reference_n = int(np.sum(inside & crop))
        clear_n = int(np.sum(inside & valid))
        veg = inside & vegetation
        count = int(veg.sum())
        if count < 5 or clear_n < .5*reference_n:
            continue
        # Means over >=5 pixels are aggregate outputs, not original pixel spectra.
        mean_spectrum = np.mean(cube[:, veg], axis=1)
        ndvi, position, slope = red_edge_metrics(wl, mean_spectrum)
        b = baseline.loc[cell]
        rows.append(dict(cell_id=cell, acquisition_utc=item_date(item), scene_id=item['id'],
                         baseline_status=b['status'], reference_pixels=reference_n,
                         clear_crop_pixels=clear_n, vegetated_pixels=count,
                         clear_crop_fraction=clear_n/reference_n,
                         spectral_ndvi=float(ndvi[0]), red_edge_peak_nm=float(position[0]),
                         red_edge_slope_per_nm=float(slope[0]),
                         historical_median_delta_NDVI=b['median_delta_NDVI']))
        spectra.append(mean_spectrum)
    if not rows:
        raise ValueError('No cell had >=5 usable vegetated pixels and >=50% clear crop coverage.')
    table = pd.DataFrame(rows)
    table.to_csv(out / 'enmap_cell_summary.csv', index=False)
    spectra = np.asarray(spectra)
    wide = pd.DataFrame(spectra, columns=[f'R_{v:.3f}nm' for v in wl])
    wide.insert(0, 'cell_id', table.cell_id.to_numpy())
    wide.to_csv(out / 'mean_cell_spectra.csv', index=False)
    baseline.reset_index().merge(table.drop(columns=['baseline_status']), on='cell_id', how='left').to_csv(
        out / 'sentinel_screening_with_enmap_context.csv', index=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    colours = {'Review lower greenness': '#de7e20', 'Smaller net change': '#3e947f',
               'Higher greenness': '#3a80b5', 'Limited reference cropland': '#999999'}
    for group, ix in table.groupby('baseline_status').groups.items():
        if group not in colours or group == 'Limited reference cropland':
            continue
        group_spectra = spectra[np.asarray(list(ix))]
        ax.plot(wl, np.median(group_spectra, axis=0), color=colours[group],
                label=f'{group} (n={len(ix)} cells)')
    ax.set(xlabel='Wavelength (nm)', ylabel='Surface reflectance (unitless)',
           title=f'EnMAP spectral context — {item_date(item)[:10]}\nGroups from Sentinel-2 2023–2024 screening')
    ax.legend(fontsize=8)
    ax.grid(alpha=.2)
    fig.text(.02, .01, 'Group differences may reflect crop type, season or management; no degradation diagnosis.', fontsize=8)
    fig.tight_layout(rect=(0, .035, 1, 1))
    fig.savefig(out / 'enmap_red_edge_spectra.png', dpi=160)
    plt.close(fig)
    year = item_date(item)[:4]
    details = dict(state='analysis_complete', hyperspectral_pixels_processed=True,
        scene_id=item['id'], acquisition_utc=item_date(item), cells_with_spectra=len(table),
        review_cells_with_spectra=int((table.baseline_status == 'Review lower greenness').sum()),
        usable_red_edge_estimates=int(table.red_edge_peak_nm.notna().sum()),
        wavelengths_nm=wl.tolist(), native_resolution_m=[abs(transform.a), abs(transform.e)],
        temporal_relationship='Within baseline years; not a matched-date validation.' if year in ['2023','2024']
                              else 'Outside 2023–2024 baseline. Later/earlier context only; not historical validation.',
        attribution=f'Contains modified EnMAP data ©DLR [{year}].',
        scene_citation=item['properties'].get('sci:citation', ''),
        method='650–850 nm subset; land, cloud/shadow/haze/cirrus/snow/testflags and defective-pixel screening; '
               'static 2021 crop reference; NDVI >=0.30; means of >=5 vegetated native pixels per cell; '
               '3-band mean smoothing; largest reflectance gradient in 690–750 nm; boundary peaks withheld.',
        limitations='Exploratory, unvalidated spectral shape. Crop types/stages are not controlled. '
                    'No concentration estimates, causal diagnosis, accuracy score or revision of original flags.',
        reproducibility='Original STAC item and code provided; pixel access requires DLR account. '
                        'Private NPZ cache and full imagery are excluded from public export.',
        updated_utc=datetime.now(timezone.utc).isoformat())
    write_json(out / 'hyperspectral_status.json', details)
    (out / 'READ_ME.txt').write_text(details['attribution']+'\n'+details['temporal_relationship']+'\n'+
        details['limitations']+'\n'+details['reproducibility']+'\n', encoding='utf-8')
    return table, details


def attach_to_dashboard(root, details):
    """Add current EnMAP evidence to the same offline dashboard and selected cell."""
    import re
    import html
    import base64
    root = Path(root)
    path = root/'results/START_HERE.html'
    page = path.read_text(encoding='utf-8')
    base = root/'work/dashboard_without_enmap.html'
    if 'id="hyperspectral-summary"' in page:
        if not base.exists():
            raise ValueError('Rerun Notebook 04 step 4 to recreate the base dashboard, then step 5.')
        page = base.read_text(encoding='utf-8')
    else:
        base.parent.mkdir(parents=True, exist_ok=True)
        base.write_text(page, encoding='utf-8')
    match = re.search(r'(<script id="reclaim-data" type="application/json">)(.*?)(</script>)', page, re.S)
    if not match:
        raise ValueError('Expected RECLAIM dashboard payload was not found.')
    payload = json.loads(match.group(2))
    completed = details.get('state') == 'analysis_complete'
    by_cell = {}
    if completed:
        table = pd.read_csv(root/'results/hyperspectral/enmap_cell_summary.csv')
        by_cell = {r['cell_id']: r for r in json.loads(table.to_json(orient='records'))}
    payload['hyperspectral'] = dict(completed=completed, metadata=details, cells=by_cell)
    encoded = json.dumps(payload, separators=(',', ':')).replace('<', '\\u003c')
    page = page[:match.start(2)] + encoded + page[match.end(2):]
    if completed:
        text = (f"EnMAP hyperspectral observation: {details['acquisition_utc'][:10]}. "
                f"{details['cells_with_spectra']} cells have usable spectra, including "
                f"{details['review_cells_with_spectra']} of the original investigation candidates. "
                + details['temporal_relationship'])
        png = base64.b64encode((root/'results/hyperspectral/enmap_red_edge_spectra.png').read_bytes()).decode()
        visual = '<img style="width:100%;max-width:1000px" alt="EnMAP vegetation spectra by Sentinel screening group" src="data:image/png;base64,'+png+'">'
        note = html.escape(details['attribution'])
    else:
        text = ('Hyperspectral data has not been analysed for this run. The map and shortlist use '
                'Sentinel-2 multispectral measurements from 2023–2024. EnMAP status: '
                + str(details.get('state', 'not_available')) + '.')
        visual, note = '', 'No EnMAP scene, spectral result or hyperspectral bonus is claimed.'
    section = ('<section class="panel" id="hyperspectral-summary"><h2>Data used and spectral context</h2><p>'
               + html.escape(text) + '</p>' + visual + '<p class="muted">' + note + '</p></section>')
    page = page.replace('</main>', section+'</main>', 1)
    marker = '<div id="detail" aria-live="polite"></div>'
    page = page.replace(marker, marker+'<div id="hyper-cell" aria-live="polite"></div>', 1)
    insertion = " const holder=document.getElementById('charts');"
    if insertion not in page:
        raise ValueError('Expected dashboard cell-selection hook was not found.')
    page = page.replace(insertion, ' showHyperspectral(id);\n'+insertion, 1)
    function = '''
function showHyperspectral(id){
 const box=document.getElementById('hyper-cell');box.replaceChildren();
 const title=document.createElement('h3');title.textContent='Hyperspectral evidence for this cell';box.appendChild(title);
 const p=document.createElement('p'),H=D.hyperspectral,r=H.cells[id];
 if(!H.completed){p.textContent='Not yet available. This cell is assessed using Sentinel-2 only.';}
 else if(!r){p.textContent='No EnMAP result passed the pixel/coverage rules for this cell. Missing data is not evidence of degradation.';}
 else{p.textContent='EnMAP '+r.acquisition_utc.slice(0,10)+'; '+r.vegetated_pixels+' usable vegetated pixels. '+
  'Exploratory red-edge peak: '+(r.red_edge_peak_nm===null?'withheld':r.red_edge_peak_nm.toFixed(1)+' nm')+
  '. This is spectral context, not a diagnosis or a replacement for the 2023–2024 comparison.';}
 box.appendChild(p);
}
'''
    page = page.replace('function selectCell(id){', function+'\nfunction selectCell(id){', 1)
    path.write_text(page, encoding='utf-8')
    provenance = root/'results/method_and_provenance.json'
    p = json.loads(provenance.read_text())
    p['hyperspectral'] = details
    write_json(provenance, p)
    inventory = ('DATA USED IN THIS RUN\n\n'
                 'Sentinel-2A/B: multispectral L2A; January 2023 through December 2024.\n'
                 'ESA WorldCover: 2021 land-cover reference, class 40 for cropland.\n'
                 'Availability search: 2016–2025 catalogue metadata only.\n'
                 'No machine-learning model was trained.\n\n')
    if completed:
        inventory += (f"EnMAP: hyperspectral L2A; acquired {details['acquisition_utc']}.\n"
                      f"Scene: {details['scene_id']}\n"
                      f"Cells with spectra: {details['cells_with_spectra']}; original review candidates with spectra: "
                      f"{details['review_cells_with_spectra']}.\n"
                      +details['temporal_relationship']+'\n'+details['attribution']+'\n')
    else:
        inventory += 'EnMAP: no hyperspectral measurements analysed in this run.\nStatus: '+str(details.get('state'))+'\n'
    inventory += ('\nBUSINESS OUTPUT\nThe map and shortlist help advisers select locations for field checks. '
                  'Flags are not verified degradation. Profit, savings, cause and rehabilitation benefit '
                  'have not been measured.\n')
    (root/'results/DATA_USED.txt').write_text(inventory, encoding='utf-8')
