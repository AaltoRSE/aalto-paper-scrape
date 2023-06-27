import argparse
import itertools
import json
import os
from os.path import join
import pathlib
import subprocess
import tempfile
from urllib.parse import urlparse, parse_qs, urlencode
import xml.etree.ElementTree as ET
import zipfile

import dateutil.parser
import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('start')
    parser.add_argument('--max-iter')
    args = parser.parse_args()

    ns = {
        "oai": "http://www.openarchives.org/OAI/2.0/",
        "dcterms": "http://purl.org/dc/terms/",
        "kk": "http://www.kansalliskirjasto.fi/oai",
        }

    url = args.start

    data = zipfile.ZipFile('data.zip', 'a')

    # PDF temporary directories
    pdftmpdir = tempfile.TemporaryDirectory(dir=os.environ['XDG_RUNTIME_DIR'], prefix='scrape')

    for i in itertools.count():
        print()
        print(url)
        # Get the page
        r = requests.get(url)
        page = ET.fromstring(r.text)
        page_data = {
            'i': 0,
            "url": url,
            "page": r.text,
        }
        data.open(f'page/{i:06d}.json', 'w').write(json.dumps(page_data).encode())

        # Get all records
        records = page.findall(".//oai:record", ns)

        # Parse all records
        for record in records:
            identifier = record.find('.//oai:identifier', ns).text.replace('/', '%2F')
            #abstract = record.find('.//dcterms:abstract', ns).text
            date = dateutil.parser.parse(record.find('.//dcterms:issued', ns).text)
            year = date.year
            record_str = ET.tostring(record)

            files = record.findall('.//kk:file', ns)
            #for file in files:
            #    fname = file.attrib['href']
            fnames = { f.attrib['href']: os.path.join(pdftmpdir.name, f'{i:04}.pdf') 
                      for (i,f) in enumerate(files) }
            # Download and save
            for url, fname in fnames.items():
                open(fname, 'wb').write(requests.get(url).content)
            # Combine all PDFs
            pdf_combined = join(pdftmpdir.name, 'combined.pdf')
            cmd = ['pdftk', ] + list(fnames.values()) + ['cat', 'output', pdf_combined]
            print(cmd)
            #import IPython ; IPython.embed()
            subprocess.call(cmd)
            combined = open(pdf_combined, 'rb').read()

            # Save to zipfile
            data.open(f'pdf-combined/{year}/{identifier}.pdf', 'w').write(combined)
            data.open(f'record/{year}/{identifier}.xml', 'w').write(record_str)



        # Find resumption 
        rt_element = page.find('.//oai:resumptionToken', ns)
        print(rt_element)
        if rt_element is None:
            import IPython ; IPython.embed()
            break
        rt = rt_element.text
        # Construct new URL
        u = urlparse(args.start)
        query = parse_qs(u.query)
        del query['set']
        del query['metadataPrefix']
        query['resumptionToken'] = [rt]
        url = u._replace(query=urlencode(query, doseq=True, safe='/')).geturl()
        #exit(1)

if __name__ == "__main__":
    main()