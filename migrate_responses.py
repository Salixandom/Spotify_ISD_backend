#!/usr/bin/env python3
"""
Helper script to migrate Response() calls to standard response classes.
Run this from the services directory.
"""

import re
import sys
from pathlib import Path


def migrate_response_calls(file_path):
    """Migrate Response() calls to standard response classes in a file."""

    with open(file_path, 'r') as f:
        content = f.read()

    original_content = content
    changes_made = 0

    # Add imports if not present
    if 'from utils.responses import' not in content and 'from utils.response import' not in content:
        # Find the imports section
        import_section = re.search(r'^(from rest_framework.*\n)+', content, re.MULTILINE)
        if import_section:
            last_import_end = import_section.end()
            new_imports = "\nfrom utils.responses import (\n    SuccessResponse,\n    ErrorResponse,\n    NotFoundResponse,\n    ForbiddenResponse,\n    ValidationErrorResponse,\n)\n"
            content = content[:last_import_end] + new_imports + content[last_import_end:]
            print(f"  ✓ Added response imports")
            changes_made += 1

    # Pattern 1: Response with status.HTTP_404_NOT_FOUND
    pattern1 = r"return Response\(\{'valid': False\}, status=status\.HTTP_404_NOT_FOUND\)"
    replacement1 = "return NotFoundResponse(message='Invalid link')"
    content, count1 = re.subn(pattern1, replacement1, content)
    changes_made += count1
    if count1:
        print(f"  ✓ Migrated {count1} NotFound responses")

    # Pattern 2: Response with status.HTTP_403_FORBIDDEN
    pattern2 = r"return Response\(\{'error': 'Forbidden'\}, status=status\.HTTP_403_FORBIDDEN\)"
    replacement2 = "return ForbiddenResponse(message='Access forbidden')"
    content, count2 = re.subn(pattern2, replacement2, content)
    changes_made += count2
    if count2:
        print(f"  ✓ Migrated {count2} Forbidden responses")

    # Pattern 3: Response with status.HTTP_404_NOT_FOUND (error key)
    pattern3 = r"return Response\(\{'error': 'Playlist not found'\}, status=status\.HTTP_404_NOT_FOUND\)"
    replacement3 = "return NotFoundResponse(message='Playlist not found')"
    content, count3 = re.subn(pattern3, replacement3, content)
    changes_made += count3
    if count3:
        print(f"  ✓ Migrated {count3} NotFound responses (error)")

    # Pattern 4: Response with status.HTTP_400_BAD_REQUEST
    pattern4 = r"return Response\(\{'error': '.*?'\}, status=status\.HTTP_400_BAD_REQUEST\)"
    replacement4 = r"return ErrorResponse(error='validation_error', message='\g<0>')"
    content, count4 = re.subn(pattern4, replacement4, content)
    changes_made += count4
    if count4:
        print(f"  ✓ Migrated {count4} BadRequest responses")

    # Pattern 5: Response with status.HTTP_201_CREATED
    pattern5 = r"return Response\((.*?)\), status=status\.HTTP_201_CREATED\)"
    replacement5 = r"return SuccessResponse(data=\1, message='Created successfully', status_code=201)"
    content, count5 = re.subn(pattern5, replacement5, content)
    changes_made += count5
    if count5:
        print(f"  ✓ Migrated {count5} Created responses")

    # Pattern 6: Response with status.HTTP_200_OK
    pattern6 = r"return Response\((.*?)\), status=status\.HTTP_200_OK\)"
    replacement6 = r"return SuccessResponse(data=\1)"
    content, count6 = re.subn(pattern6, replacement6, content)
    changes_made += count6
    if count6:
        print(f"  ✓ Migrated {count6} OK responses")

    # Pattern 7: Response with status.HTTP_204_NO_CONTENT
    pattern7 = r"return Response\(status=status\.HTTP_204_NO_CONTENT\)"
    replacement7 = "return Response(status=status.HTTP_204_NO_CONTENT)"
    content, count7 = re.subn(pattern7, replacement7, content)
    changes_made += count7
    if count7:
        print(f"  ✓ Kept {count7} NoContent responses (already standard)")

    if changes_made > 0 and content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✅ Saved {changes_made} changes to {file_path.name}")
        return True
    elif changes_made == 0:
        print(f"  ℹ️  No changes needed for {file_path.name}")
        return True
    else:
        print(f"  ⚠️  No changes made to {file_path.name}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python migrate_responses.py <views_file>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"\n🔄 Migrating: {file_path}")
    migrate_response_calls(file_path)
    print()


if __name__ == "__main__":
    main()
