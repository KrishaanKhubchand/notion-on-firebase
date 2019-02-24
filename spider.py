import notion
import traceback
import os
import pickledb
import sys
import json
import pdb
import shutil


'''
requires notion.py be in the same directory as this module
notion.py can be found at http://github.com/shariq/notion-on-firebase
'''


def notion_spider(root_page):
    # page in this function means a notion page identifier
    # like b9b2d96c8e844556be0740771db875a3

    # eventually this should check the last updated timestamp and
    # request pages which are out of date...

    spider_results = {}
    to_scrape = [root_page]  # should be a deque, but ew dependencies
    while len(to_scrape):
        page = to_scrape.pop(0)
        # shifting everything in memory over by one... so what lol
        if page in spider_results:
            continue
        print 'now scraping', page
        try:
            html, new_pages = notion.scrape_notion_page(page)
        except Exception:
            print 'encountered error while scraping', page
            traceback.print_exc()
            print 'skipping', page, 'for now'
            continue
        spider_results[page] = html
        # dumping to disk is nice for resuming after crash
        for new_page in new_pages:
            if new_page not in spider_results and new_page not in to_scrape:
                to_scrape.append(new_page)
    return spider_results


def dump_results(results, results_path='./results'):
    for page, html in results.items():
        path = os.path.join(results_path, page + '.html')
        with open(path, 'w') as handle:
            handle.write(html.encode('utf8'))


def postprocess(results_path='./results', rewrite_db_path='rewrite.db'):
    pages = [
        str(page.replace('.html', '')) for page in os.listdir(results_path)
        if '.html' in page and len(page) == 32+5]
    paths = [os.path.join(results_path, page + '.html') for page in pages]
    htmls = [open(path).read() for path in paths]
    rewrite_db = pickledb.load(rewrite_db_path, True)
    for page, html in zip(pages, htmls):
        page_to_path_mapping = rewrite_db.get(page)
        should_keep_page_to_path_mapping = True
        if page_to_path_mapping:
            should_keep_page_to_path_mapping = get_bool_from_prompt('Page {} is mapped to path {}. Would you like to keep this mapping? [y/N]'.format(page, page_to_path_mapping))
        if not page_to_path_mapping or not should_keep_page_to_path_mapping:
            print 'What should the path of page {} be? If you\'d like the page to be the homepage, just write index.'.format(page)
            title_index = html.index('<title>')
            print '[Only alphanumeric characters and hyphens please]'
            print html[title_index:title_index+150]
            short_url = str(raw_input(''))
            rewrite_db.set(page, short_url)
    for path, page, html in zip(paths, pages, htmls):
        print 'postprocessing', path, '...'
        processed_html = html[:].decode('utf8')
        for page in pages:
            short_url = rewrite_db.get(page)
            processed_html = processed_html.replace(
                'https://www.notion.so/' + page, '/' + short_url)
        with open(path, 'w') as handle:
            handle.write(processed_html.encode('utf8'))


def get_bool_from_prompt(prompt):
    while True:
        try:
            meow = {"y": True, "n": False}[raw_input(prompt).lower()[0]]
            return meow
        except Exception:
            print("Invalid input. Please enter y or n.")


def generate_rewrites(results_path='./results', rewrite_db_path='rewrite.db'):
    rewrites = []
    pages = [
        page.replace('.html', '') for page in os.listdir(results_path)
        if '.html' in page and len(page) == 32+5]
    rewrite_db = pickledb.load(rewrite_db_path, True)
    index_page_is_configured = False
    for page in pages:
        rewrite = {}
        new_page_path = rewrite_db.get(page)
        if not new_page_path == 'index':
            rewrite['source'] = '/' + new_page_path
            rewrite['destination'] = '/' + page + '.html'
            rewrites.append(rewrite)
        else:
            index_page_is_configured = True
            rename_index_html(new_page_path, page, results_path)
    if not index_page_is_configured:
        try:
            # Erase index.html if it's not configured.
            os.remove('{}/index.html'.format(results_path))
        except Exception:
            print 'Failed to erase index.html from public folder, it probably didn\'t exist'
    return rewrites


def rename_index_html(new_page_path, page, results_path):
    shutil.move('{}/{}.html'.format(results_path, page), '{}/{}.html'.format(results_path, new_page_path))

def run(root_page, results_path='./results'):
    results = notion_spider(root_page)
    dump_results(results, results_path)
    postprocess(results_path)
    rewrites = generate_rewrites(results_path)
    print json.dumps(rewrites)
    return rewrites


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print 'This script dumps spider results to the results directory.'
        print 'usage: python spider.py <root_page>'
        print 'e.g, python spider.py d065149ff38a4e7a9b908aeb262b0f4f'
        sys.exit(-1)
    root_page = sys.argv[-1]
    run(root_page)
