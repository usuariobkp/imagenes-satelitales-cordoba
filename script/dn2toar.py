#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para GRASS GIS que procesa imágenes de Landsat de DNs a Reflectancia ToA.
Aplica una corrección atmosférica con el método DOS (Dark Object Substraction).

Para que funcione correctamente, se debe ejecutar dentor de una sesión de GRASS.

"""
import sys
import os
import glob
from grass import script as g

def load_files(root, fname):
    path = os.path.join(root, fname)
    raster_name, _ = os.path.splitext(fname)

    # Para Landsat 7, renombra el nombre de las bandas de temperatura:
    #   * B6_VCID_1 -> B61
    #   * B6_VCID_2 -> B62
    if 'VCID' in raster_name:
        prefix, num = raster_name.split('_VCID_')
        raster_name = prefix + num

    g.message('Loading {}'.format(raster_name))
    g.run_command('r.in.gdal', flags='e', input=path,
            output=raster_name, quiet=True, overwrite=True)

def convert_dn_to_toar(root, product_id):
    g.message('Applying ToA reflectance conversion to {}'.format(root))
    metfile = os.path.join(root, '{}_MTL.txt'.format(product_id))
    g.run_command('i.landsat.toar', input='{}_B'.format(product_id),
            output='{}_TOAR_B'.format(product_id), metfile=metfile,
            method='dos3')

def export_toar_files(root, fname):
    output_root = os.path.join(root, '{}.TIF'.format(fname))

    g.message('Exporting {}'.format(fname))
    g.run_command('r.out.gdal', flags='c', input=fname, output=output_root,
            format='GTiff', type='Float64', overwrite=True,
            createopt='profile=GeoTIFF,compress=lzw')

def remove_all_rasters():
    """Remove all loaded rasters"""
    for fname in g.list_grouped(['raster'])['PERMANENT']:
        g.run_command('g.remove', flags='f', type='raster',
                name=fname)

def all_scenes(input_dir):
    landsat_dirs = glob.glob(os.path.join(input_dir, 'LANDSAT_*/'))

    for ldir in landsat_dirs:
        for root, _, files in os.walk(ldir):
            tif_files = [f for f in files if f.lower().endswith('.tif')
                    if '_TOAR_' not in f]
            if tif_files:
                yield root, tif_files


if __name__ == '__main__':
    import argparse
    import multiprocessing
    from functools import partial

    parser = argparse.ArgumentParser(
            description='Convierte DNs de imágenes Landsat a reflectancia ToA')
    parser.add_argument('--input-dir', '-i', default='/data',
            help='Ruta donde están almacenadas las imágenes')
    args = parser.parse_args()

    count = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(count)

    for root, tif_files in all_scenes(args.input_dir):
        product_id = root.split('/')[-1]
        g.message('Working on {}'.format(product_id))

        try:
            # Load
            load_worker = partial(load_files, root)
            pool.map(load_worker, tif_files)
            # Process
            convert_dn_to_toar(root, product_id)
            # Export
            loaded_files = g.list_grouped(['raster'], pattern='*_TOAR_*')['PERMANENT']
            export_worker = partial(export_toar_files, root)
            pool.map(export_worker, loaded_files)
        finally:
            remove_all_rasters()

    print('All done! You can exit now (Ctrl+D)')
