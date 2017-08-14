# Written by Daniel Pesch, daniel.pesch@whu.edu, 2015
# This is an old script to retrieve a single page (up to a maximum of 100 filings per query) of filings from EDGAR
# Should be refactored to use DOM traversal instead of index-based extraction as it already does for resolving Tickers

import getopt
import os.path
import socket
import ssl
import sys
import time
import xml.etree.ElementTree as ET
from urllib.error import URLError, HTTPError
from urllib.request import urlopen

# This is a very unsafe monkeypatch
# We have to do this because the SEC recently switched from only using plaintext HTTP to enforcing HTTPS with
# a 301 Redirect for all pages. To avoid the necessity
ssl._create_default_https_context = ssl._create_unverified_context


def download_file(source_url, target_filename):
    # print('Saving to:', str(target_filename))
    mem_file = ""
    good_read = False
    if os.path.isfile(target_filename):
        print("Local copy already exists")
        return True
    else:
        print("Downloading:", source_url)
        try:
            target_file = urlopen(source_url)
            try:
                mem_file = target_file.read()
                good_read = True
            finally:
                target_file.close()
        except HTTPError as e:
            print("HTTP Error:", e.code)
        except URLError as e:
            print("URL Error:", e.reason)
        except TimeoutError as e:
            print("Timeout Error:", e.reason)
        except socket.timeout:
            print("Socket Timeout Error")
        if good_read:
            output = open(target_filename, 'wb')
            output.write(mem_file)
            output.close()
        return good_read


def download_specific_filing_for_company(filing_type, cik, protocol):
    try:
        edgar_root_url = 'http://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=' + cik + '&type=' + filing_type + '&dateb=&owner=exclude&count=400'
        edgar_root_url_result = urlopen(edgar_root_url)
        try:
            edgar_root_url_data = str(edgar_root_url_result.read())
            while True:
                try:
                    if edgar_root_url_data.index('/Archives/edgar/data/' + cik) > 0:
                        start = int(edgar_root_url_data.index('/Archives/edgar/data/' + cik))
                        end = int(edgar_root_url_data.index('"', start))
                        filing_link = edgar_root_url_data[start:end]
                        if not os.path.exists("sec/" + filing_type + "/" + filing_link.split('/')[4]):
                            os.makedirs("sec/" + filing_type + "/" + filing_link.split('/')[4])
                        try:
                            specific_filing_url = urlopen("http://www.sec.gov/" + filing_link)
                            try:
                                specific_filing_url_data = specific_filing_url.read()
                                specific_filing_url_data = str(specific_filing_url_data)
                                # URL start and end
                                specific_filing_url_start = int(
                                    specific_filing_url_data.index('<td scope="row"><a href="')) + 25
                                specific_filing_url_end = int(
                                    specific_filing_url_data.index('">', specific_filing_url_start))
                                # Date start and end
                                specific_filing_date_start = int(
                                    specific_filing_url_data.index('<div class="infoHead">Filing Date</div>')) + 68
                                specific_filing_date_end = int(
                                    specific_filing_url_data.index('</div>', specific_filing_date_start))

                                substring_date = specific_filing_url_data[
                                                 specific_filing_date_start:specific_filing_date_end]
                                substring_url = specific_filing_url_data[
                                                specific_filing_url_start:specific_filing_url_end]

                                # old filings might still be in text form and therefore have to be treated separately
                                if substring_url.split("/")[int(len(substring_url.split("/")) - 1)]:
                                    download_file("http://www.sec.gov/" + substring_url,
                                                  "sec/" + filing_type + "/" + filing_link.split('/')[
                                                      4] + '/' + substring_date.replace('-', '_') + '_' +
                                                  filing_link.split('/')[int(len(filing_link.split('/'))) - 1])
                            finally:
                                specific_filing_url.close()
                        except HTTPError as e:
                            print("HTTP Error:", e.code)
                        except URLError as e:
                            print("URL Error:", e.reason)
                        except TimeoutError as e:
                            print("Timeout Error:", e.reason)
                        except socket.timeout:
                            print("Socket Timeout Error")
                        # store transmission protocols
                        if protocol == "true":
                            download_file("http://www.sec.gov/" + filing_link,
                                          "sec/" + filing_type + "/" + filing_link.split('/')[4] + '/transmission_' +
                                          filing_link.split('/')[int(len(filing_link.split('/'))) - 1])
                        edgar_root_url_data = edgar_root_url_data[end:len(edgar_root_url_data)]
                except ValueError:
                    break
        finally:
            edgar_root_url_result.close()
    except HTTPError as e:
        print("HTTP Error:", e.code)
    except URLError as e:
        print("URL Error:", e.reason)
    except TimeoutError as e:
        print("Timeout Error:", e.reason)
    except socket.timeout:
        print("Socket Timeout Error")


def lookup_cik(ticker):
    # Given a ticker symbol, retrieves the CIK
    good_read = False
    ticker = ticker.strip().upper()
    url = 'http://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&count=10&output=xml'.format(cik=ticker)
    root = None
    xml_data = None
    try:
        xml_file = urlopen(url)
        try:
            xml_data = xml_file.read()
            good_read = True
        finally:
            xml_file.close()
    except HTTPError as e:
        print("HTTP Error:", e.code)
    except URLError as e:
        print("URL Error:", e.reason)
    except TimeoutError as e:
        print("Timeout Error:", e.reason)
    except socket.timeout:
        print("Socket Timeout Error")
    if not good_read:
        print("Unable to lookup CIK for ticker:", ticker)
        return

    if xml_data is not None:
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as parsing_error:
            print("XML Parser Error:", parsing_error)

    if root is not None:
        try:
            cik_element = list(root.iter("CIK"))[0]
            return cik_element.text.lstrip("0")
        except StopIteration:
            pass


def main(argv):
    if not os.path.exists("sec"):
        os.makedirs("sec")
    socket.setdefaulttimeout(10)
    start_time = time.time()
    type = "10-Q"
    store_transmission_protocol = "false"
    symbol = "AAPL"
    cik = "320193"
    try:
        opts, args = getopt.getopt(argv, "t:c:p:s:", ["type=", "cik=", "protocol=", "symbol="])
    except getopt.GetoptError:
        print('getSpecificFilingType -t <type> -c <cik> -p <protocol>  -s <symbol> | -h <help>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('getSpecificFilingType -t <type> -c <cik> -p <protocol> -s <symbol> | -h <help>')
            sys.exit()
        elif opt in ("-t", "--type"):
            type = arg
        elif opt in ("-c", "--cik"):
            cik = arg
        elif opt in ("-p", "--protocol"):
            store_transmission_protocol = arg
        elif opt in ("-s", "--symbol"):
            symbol = arg
    else:
        if symbol != "":
            cik = lookup_cik(symbol)
        download_specific_filing_for_company(type, cik, store_transmission_protocol)
    end_time = time.time()
    print("Elapsed time:", end_time - start_time, "seconds")


if __name__ == "__main__":
    main(sys.argv[1:])
