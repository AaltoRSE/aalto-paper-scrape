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
    parser.add_argument('output')
    parser.add_argument('--max-iter')
    parser.add_argument('--verbose', '-v')
    args = parser.parse_args()

    ns = {
        "oai": "http://www.openarchives.org/OAI/2.0/",
        "dcterms": "http://purl.org/dc/terms/",
        "kk": "http://www.kansalliskirjasto.fi/oai",
        }

    N_papers = 0
    url = args.start
    # PDF temporary directories
    pdftmpdir = tempfile.TemporaryDirectory(dir=os.environ['XDG_RUNTIME_DIR'], prefix='scrape')

    with zipfile.ZipFile(args.output, 'a') as data:
        namelist = set(data.namelist())
        #print(namelist)


        for i in itertools.count():
            print()
            print(f'{i:-5} {url}')
            # Get the page
            r = requests.get(url)
            page = ET.fromstring(r.text)
            page_data = {
                'i': 0,
                "url": url,
                "page": r.text,
            }
            #data.open(f'listing/{i:06d}.json', 'w').write(json.dumps(page_data).encode())

            # Get all records
            records = page.findall(".//oai:record", ns)

            # Parse all records
            for record in records:
                identifier = record.find('.//oai:identifier', ns).text.replace('/', '%2F')

                # Has this been deleted?
                if record.find(".//oai:header[@status='deleted']", ns):
                    print("    record deleted")
                    continue

                # Get basic info
                date = dateutil.parser.parse(record.find('.//dcterms:issued', ns).text)
                year = date.year
                print(f'    {N_papers:-6} {year} {identifier}')
                N_papers += 1

                # Already in archive?
                pdf_combined_name = f'pdf-combined/{year}/{identifier}.pdf'
                if pdf_combined_name in namelist:
                    print('    already present')
                    continue

                #abstract = record.find('.//dcterms:abstract', ns).text
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
                #print(cmd)
                #import IPython ; IPython.embed()
                subprocess.call(cmd)
                # combining may not succeed.  In which case, ignore.
                if not os.access(pdf_combined, os.F_OK):
                    print('    PDF not combined')
                    continue
                combined = open(pdf_combined, 'rb').read()
                os.unlink(pdf_combined)

                # Save to zipfile
                data.open(pdf_combined_name, 'w').write(combined)
                data.open(f'record/{year}/{identifier}.xml', 'w').write(record_str)



            # Find resumption
            rt_element = page.find('.//oai:resumptionToken', ns)
            #print(rt_element)
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
