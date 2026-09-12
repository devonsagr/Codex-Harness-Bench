from text_utils import normalize_text


def search_notes(notes, query, include_archived=False):
    return [note for note in notes if query in note.get("title", "")]
