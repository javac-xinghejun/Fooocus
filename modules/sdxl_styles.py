import os
import re
import json
import math
import modules.config

from modules.util import get_files_from_folder

# cannot use modules.config - validators causing circular imports
styles_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../sdxl_styles/'))
wildcards_max_bfs_depth = 64


def normalize_key(k):
    k = k.replace('-', ' ')
    words = k.split(' ')
    words = [w[:1].upper() + w[1:].lower() for w in words]
    k = ' '.join(words)
    k = k.replace('3d', '3D')
    k = k.replace('Sai', 'SAI')
    k = k.replace('Mre', 'MRE')
    k = k.replace('(s', '(S')
    return k


styles = {}

styles_files = get_files_from_folder(styles_path, ['.json'])

for x in ['sdxl_styles_fooocus.json',
          'sdxl_styles_sai.json',
          'sdxl_styles_mre.json',
          'sdxl_styles_twri.json',
          'sdxl_styles_diva.json',
          'sdxl_styles_marc_k3nt3l.json']:
    if x in styles_files:
        styles_files.remove(x)
        styles_files.append(x)

for styles_file in styles_files:
    try:
        with open(os.path.join(styles_path, styles_file), encoding='utf-8') as f:
            for entry in json.load(f):
                name = normalize_key(entry['name'])
                prompt = entry['prompt'] if 'prompt' in entry else ''
                negative_prompt = entry['negative_prompt'] if 'negative_prompt' in entry else ''
                styles[name] = (prompt, negative_prompt)
    except Exception as e:
        print(str(e))
        print(f'Failed to load style file {styles_file}')

style_keys = list(styles.keys())
fooocus_expansion = "Fooocus V2"
legal_style_names = [fooocus_expansion] + style_keys


SD_XL_BASE_RATIOS = {
    "0.45": (900, 1990),
    "0.67": (1024, 1536),
    "1.5": (1536, 1024),
    "0.5": (704, 1408),
    "0.52": (704, 1344),
    "0.57": (768, 1344),
    "0.6": (768, 1280),
    "0.68": (832, 1216),
    "0.72": (832, 1152),
    "0.78": (896, 1152),
    "0.82": (896, 1088),
    "0.88": (960, 1088),
    "0.94": (960, 1024),
    "1.0": (1024, 1024),
    "1.07": (1024, 960),
    "1.13": (1088, 960),
    "1.21": (1088, 896),
    "1.29": (1152, 896),
    "1.38": (1152, 832),
    "1.46": (1216, 832),
    "1.67": (1280, 768),
    "1.75": (1344, 768),
    "1.91": (1344, 704),
    "2.0": (1408, 704),
    "2.09": (1472, 704),
    "2.4": (1536, 640),
    "2.5": (1600, 640),
    "2.89": (1664, 576),
    "3.0": (1728, 576),
}

aspect_ratios = {}
default_aspect_ratio = None

# import math

for k, (w, h) in SD_XL_BASE_RATIOS.items():
    txt = f'{w}×{h}'

    # gcd = math.gcd(w, h)
    # txt += f' {w//gcd}:{h//gcd}'
    
    aspect_ratios[txt] = (w, h)
    if k == "1.29":
        default_aspect_ratio = txt


def apply_style(style, positive):
    p, n = styles[style]
    return p.replace('{prompt}', positive).splitlines(), n.splitlines()


def apply_wildcards(wildcard_text, rng, i, read_wildcards_in_order):
    for _ in range(wildcards_max_bfs_depth):
        placeholders = re.findall(r'__([\w-]+)__', wildcard_text)
        if len(placeholders) == 0:
            return wildcard_text

        print(f'[Wildcards] processing: {wildcard_text}')
        for placeholder in placeholders:
            try:
                matches = [x for x in modules.config.wildcard_filenames if os.path.splitext(os.path.basename(x))[0] == placeholder]
                words = open(os.path.join(modules.config.path_wildcards, matches[0]), encoding='utf-8').read().splitlines()
                words = [x for x in words if x != '']
                assert len(words) > 0
                if read_wildcards_in_order:
                    wildcard_text = wildcard_text.replace(f'__{placeholder}__', words[i % len(words)], 1)
                else:
                    wildcard_text = wildcard_text.replace(f'__{placeholder}__', rng.choice(words), 1)
            except:
                print(f'[Wildcards] Warning: {placeholder}.txt missing or empty. '
                      f'Using "{placeholder}" as a normal word.')
                wildcard_text = wildcard_text.replace(f'__{placeholder}__', placeholder)
            print(f'[Wildcards] {wildcard_text}')

    print(f'[Wildcards] BFS stack overflow. Current text: {wildcard_text}')
    return wildcard_text


def get_words(arrays, totalMult, index):
    if len(arrays) == 1:
        return [arrays[0].split(',')[index]]
    else:
        words = arrays[0].split(',')
        word = words[index % len(words)]
        index -= index % len(words)
        index /= len(words)
        index = math.floor(index)
        return [word] + get_words(arrays[1:], math.floor(totalMult/len(words)), index)


def apply_arrays(text, index):
    arrays = re.findall(r'\[\[(.*?)\]\]', text)
    if len(arrays) == 0:
        return text

    print(f'[Arrays] processing: {text}')
    mult = 1
    for arr in arrays:
        words = arr.split(',')
        mult *= len(words)
    
    index %= mult
    chosen_words = get_words(arrays, mult, index)
    
    i = 0
    for arr in arrays:
        text = text.replace(f'[[{arr}]]', chosen_words[i], 1)   
        i = i+1
    
    return text

