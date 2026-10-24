"""Translate and dub an authorized video, then download video and subtitles."""
import argparse
from client import add_arguments, run


def make_body(args):
    if not args.target:
        raise ValueError('--target is required for new jobs (for example es, en, ja or zh)')
    return {'type': 'video_translation', 'source_language': args.source,
            'target_language': args.target, 'manual_review': args.manual_review,
            'advanced_quality': args.advanced, 'subtitle_enabled': not args.no_subtitles}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument('--target', help='One supported target language code')
    parser.add_argument('--source', default='auto')
    parser.add_argument('--manual-review', action='store_true', help='Pause for source and translation text review')
    parser.add_argument('--advanced', action='store_true')
    parser.add_argument('--no-subtitles', action='store_true', help='Disable subtitle burn-in; retain translated voiceover')
    run(parser, make_body)
