"""
Unit tests for the AIResponseGenerator class.

This module contains tests for the AIResponseGenerator, particularly focusing on
the `tailor_resume_pdf` method's functionality, including PDF parsing,
text replacement, dynamic output path generation, and error handling.
It also tests other integrated functionalities like `resume_content` reloading.
Extensive mocking is used for external dependencies like PyPDF2 and file operations.
"""
import unittest
import os
from datetime import datetime as dt # Alias to avoid conflict with datetime class attribute
import re
from unittest.mock import patch, MagicMock, mock_open

# Attempt to import PyPDF2 and its error for PdfReadError
try:
    import PyPDF2
    PdfReadError = PyPDF2.errors.PdfReadError
except ImportError:
    # If PyPDF2 is not installed in the test environment, create a dummy error class
    class PdfReadError(Exception):
        pass
    PyPDF2 = MagicMock() # Mock PyPDF2 if not available
    PyPDF2.errors.PdfReadError = PdfReadError


from src.ai.ai_response_generator import AIResponseGenerator

class TestAIResponseGenerator(unittest.TestCase):
    """
    Test suite for the AIResponseGenerator class.

    This class sets up a common environment for testing the AIResponseGenerator,
    including mock data for personal information, experience, resume paths, etc.
    It uses unittest.mock to patch external dependencies like PyPDF2,
    file I/O operations (`open`), and datetime functions to ensure tests are
    deterministic and isolated.

    Key areas tested include:
    - PDF resume tailoring (`tailor_resume_pdf` method).
    - Correct handling of skill replacements (case-insensitive).
    - Dynamic generation of output filenames with timestamps.
    - Error handling for file operations and PDF processing.
    - Interaction between resume tailoring and resume content loading.
    """

    def setUp(self):
        """Sets up the test environment before each test method."""
        self.mock_personal_info = {
            'First Name': 'Test', 'Last Name': 'User', 'City': 'Testville', 'State': 'TS'
        }
        self.mock_experience = {'currentRole': 'Chief Tester', 'Python': '5 years'}
        self.mock_languages = {'English': 'Native'}
        self.mock_checkboxes = {'legallyAuthorized': True}
        self.mock_model_name = 'test-model'
        self.initial_resume_path = 'test_data/sample_resume.pdf' # Relative to project root for AIResponseGenerator

        # Ensure a dummy directory exists for placing test resumes if any test actually writes one
        # For most tests, actual file IO for PDFs is mocked.
        os.makedirs('test_data', exist_ok=True)

        self.generator = AIResponseGenerator(
            api_key='test_api_key',
            personal_info=self.mock_personal_info,
            experience=self.mock_experience,
            languages=self.mock_languages,
            resume_path=self.initial_resume_path,
            checkboxes=self.mock_checkboxes,
            model_name=self.mock_model_name,
            debug=True # Enable debug for more verbose logging if needed during tests
        )
        self.initial_resume_dir = self.generator.resume_dir

        # Fixed timestamp for predictable filenames
        self.fixed_datetime = dt(2024, 1, 1, 12, 0, 0)
        self.formatted_timestamp = self.fixed_datetime.strftime("%Y%m%d_%H%M%S")

    def tearDown(self):
        """Cleans up any created files after each test method if necessary."""
        # Clean up dummy files or directories if any were created by tests (not mocks)
        # These paths should match those potentially created in tests if mocks fail or if actual files are written
        paths_to_check = [
            os.path.join('test_data', f"dummy_input_tailored_{self.formatted_timestamp}.pdf"),
            os.path.join('test_data', f"sample_resume_tailored_{self.formatted_timestamp}.pdf"),
            # Add any other specific paths that might be created if needed
        ]
        for path in paths_to_check:
            if os.path.exists(path):
                os.remove(path)


    @patch('src.ai.ai_response_generator.datetime')
    @patch('src.ai.ai_response_generator.PyPDF2.PdfWriter')
    @patch('src.ai.ai_response_generator.PyPDF2.PdfReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_tailor_resume_pdf_success(self, mock_file_open, mock_pdf_reader_cls, mock_pdf_writer_cls, mock_datetime):
        """
        Tests successful PDF tailoring with dynamic path generation and state updates.

        Verifies that:
        - PyPDF2.PdfReader and PyPDF2.PdfWriter are called correctly.
        - Page text extraction and page additions to the writer occur.
        - `open` is called with a dynamically generated, timestamped output path.
        - The generator's `resume_dir` is updated to the new path.
        - The generator's `_resume_content` is reset to None.
        """
        mock_datetime.now.return_value = self.fixed_datetime

        # Configure PdfReader mock
        mock_pdf_reader_instance = MagicMock()
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Old Skill 1 and some text."
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Another page with Old Skill 2."
        mock_pdf_reader_instance.pages = [mock_page1, mock_page2]
        mock_pdf_reader_cls.return_value = mock_pdf_reader_instance

        # Configure PdfWriter mock
        mock_pdf_writer_instance = MagicMock()
        mock_pdf_writer_cls.return_value = mock_pdf_writer_instance

        replacements = [
            {'old': 'Old Skill 1', 'new': 'New Skill A'},
            {'old': 'Old Skill 2', 'new': 'New Skill B'}
        ]

        input_pdf = 'test_data/dummy_input.pdf' # This is a dummy path used as input for the method

        # Construct expected output path based on the dummy input_pdf path
        expected_dir = os.path.dirname(input_pdf) # 'test_data'
        expected_basename = f"dummy_input_tailored_{self.formatted_timestamp}.pdf"
        expected_output_path = os.path.join(expected_dir, expected_basename)


        result_path = self.generator.tailor_resume_pdf(replacements, input_pdf)

        self.assertEqual(result_path, expected_output_path)
        mock_pdf_reader_cls.assert_called_once_with(input_pdf)
        self.assertEqual(mock_page1.extract_text.call_count, 1)
        self.assertEqual(mock_page2.extract_text.call_count, 1)
        mock_pdf_writer_instance.add_page.assert_any_call(mock_page1)
        mock_pdf_writer_instance.add_page.assert_any_call(mock_page2)
        self.assertEqual(mock_pdf_writer_instance.add_page.call_count, 2)

        mock_file_open.assert_called_once_with(expected_output_path, 'wb')
        mock_pdf_writer_instance.write.assert_called_once_with(mock_file_open())

        self.assertEqual(self.generator.resume_dir, expected_output_path)
        self.assertIsNone(self.generator._resume_content)


    @patch('src.ai.ai_response_generator.datetime')
    @patch('builtins.print') # Capture print output
    @patch('src.ai.ai_response_generator.PyPDF2.PdfWriter')
    @patch('src.ai.ai_response_generator.PyPDF2.PdfReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_tailor_resume_pdf_case_insensitive_replacement(self, mock_file, mock_pdf_reader_cls, mock_pdf_writer_cls, mock_print, mock_datetime):
        """
        Tests that skill replacement in PDF text is case-insensitive.

        Verifies that:
        - A skill in the PDF text is replaced even if its casing doesn't match
          the casing of the 'old' skill in the replacements list.
        - A log message confirming case-insensitive replacement is printed.
        """
        mock_datetime.now.return_value = self.fixed_datetime

        mock_pdf_reader_instance = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Resume contains python skill and other things."
        mock_pdf_reader_instance.pages = [mock_page]
        mock_pdf_reader_cls.return_value = mock_pdf_reader_instance
        mock_pdf_writer_cls.return_value = MagicMock() # Mock PdfWriter instance

        replacements = [{'old': 'Python Skill', 'new': 'Advanced Python'}]
        input_pdf = 'test_data/dummy_input.pdf' # Dummy input path

        self.generator.tailor_resume_pdf(replacements, input_pdf)

        captured_print_output = " ".join([call.args[0] for call in mock_print.call_args_list if call.args])
        expected_log_message = "Replaced 'Python Skill' (case-insensitively) with 'Advanced Python'"
        self.assertIn(expected_log_message, captured_print_output)


    @patch('src.ai.ai_response_generator.PyPDF2.PdfReader')
    def test_tailor_resume_pdf_file_not_found(self, mock_pdf_reader_cls):
        """
        Tests error handling when the input PDF file is not found.

        Verifies that:
        - The `tailor_resume_pdf` method returns `None`.
        - The generator's `resume_dir` remains unchanged.
        """
        mock_pdf_reader_cls.side_effect = FileNotFoundError("File not found")

        initial_resume_dir = self.generator.resume_dir # Store before call
        result = self.generator.tailor_resume_pdf([], 'non_existent.pdf')

        self.assertIsNone(result)
        self.assertEqual(self.generator.resume_dir, initial_resume_dir) # Directory should not change on this error

    @patch('src.ai.ai_response_generator.PyPDF2.PdfReader')
    def test_tailor_resume_pdf_pdf_read_error(self, mock_pdf_reader_cls):
        """
        Tests error handling when PyPDF2 encounters an error reading the PDF.

        Verifies that:
        - The `tailor_resume_pdf` method returns `None`.
        - The generator's `resume_dir` remains unchanged.
        """
        global PdfReadError # Use the globally defined PdfReadError (either real or dummy)
        mock_pdf_reader_cls.side_effect = PdfReadError('Test PDF read error')

        initial_resume_dir = self.generator.resume_dir # Store before call
        result = self.generator.tailor_resume_pdf([], 'corrupted.pdf')

        self.assertIsNone(result)
        self.assertEqual(self.generator.resume_dir, initial_resume_dir) # Directory should not change


    @patch('src.ai.ai_response_generator.datetime')
    @patch('builtins.print')
    @patch('src.ai.ai_response_generator.PyPDF2.PdfWriter')
    @patch('src.ai.ai_response_generator.PyPDF2.PdfReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_tailor_resume_pdf_no_replacements_made(self, mock_file, mock_pdf_reader_cls, mock_pdf_writer_cls, mock_print, mock_datetime):
        """
        Tests behavior when no skills specified for replacement are found in the PDF.

        Verifies that:
        - The PDF is still processed, and a new (unaltered content) PDF is saved
          with a dynamic, timestamped name.
        - The generator's `resume_dir` is updated to this new path.
        - Debug logs indicate that the skills were not found for replacement.
        """
        mock_datetime.now.return_value = self.fixed_datetime

        mock_pdf_reader_instance = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Some text without the skill."
        mock_pdf_reader_instance.pages = [mock_page]
        mock_pdf_reader_cls.return_value = mock_pdf_reader_instance
        mock_pdf_writer_cls.return_value = MagicMock()

        replacements = [{'old': 'NonExistentSkill', 'new': 'SomeSkill'}]
        input_pdf = 'test_data/dummy_input.pdf'

        # Expected path construction
        expected_dir = os.path.dirname(input_pdf)
        expected_basename = f"dummy_input_tailored_{self.formatted_timestamp}.pdf"
        expected_output_path = os.path.join(expected_dir, expected_basename)

        result_path = self.generator.tailor_resume_pdf(replacements, input_pdf)
        self.assertEqual(result_path, expected_output_path) # File is still created
        self.assertEqual(self.generator.resume_dir, expected_output_path) # And resume_dir updated

        captured_print_output = " ".join([call.args[0] for call in mock_print.call_args_list if call.args])
        self.assertNotIn("Replaced 'NonExistentSkill'", captured_print_output)
        expected_debug_message = "Skill 'NonExistentSkill' not found for replacement (checked case-insensitively)"
        self.assertIn(expected_debug_message, captured_print_output)


    @patch('src.ai.ai_response_generator.datetime')
    @patch('src.ai.ai_response_generator.PyPDF2.PdfWriter')
    @patch('src.ai.ai_response_generator.PyPDF2.PdfReader')
    @patch('builtins.open', new_callable=mock_open)
    def test_resume_content_reloads_after_tailoring(self, mock_file_open, mock_pdf_reader_cls, mock_pdf_writer_cls, mock_datetime):
        """
        Tests that `resume_content` property reloads from the new path after tailoring.

        Verifies that:
        - After `tailor_resume_pdf` is called and `self.generator.resume_dir` is updated,
          a subsequent access to `self.generator.resume_content` causes `PyPDF2.PdfReader`
          to be called with the new, tailored PDF path.
        - The content returned matches the content mocked for the tailored PDF.
        """
        mock_datetime.now.return_value = self.fixed_datetime

        # --- Mocking for tailor_resume_pdf call (first use of PdfReader) ---
        mock_tailor_pdf_reader_instance = MagicMock()
        mock_tailor_page = MagicMock()
        mock_tailor_page.extract_text.return_value = "Initial resume text with OldSkill."
        mock_tailor_pdf_reader_instance.pages = [mock_tailor_page]

        mock_pdf_writer_instance = MagicMock() # For PdfWriter in tailor_resume_pdf
        mock_pdf_writer_cls.return_value = mock_pdf_writer_instance

        # --- Mocking for resume_content property call (second use of PdfReader) ---
        mock_content_pdf_reader_instance = MagicMock()
        mock_content_page = MagicMock()
        mock_content_page.extract_text.return_value = "new tailored content"
        mock_content_pdf_reader_instance.pages = [mock_content_page]

        # Configure PdfReader to be called sequentially:
        mock_pdf_reader_cls.side_effect = [mock_tailor_pdf_reader_instance, mock_content_pdf_reader_instance]

        replacements = [{'old': 'OldSkill', 'new': 'NewSkill'}]

        # self.initial_resume_path is 'test_data/sample_resume.pdf'
        # This path is used as the input_pdf_path for tailor_resume_pdf
        tailored_path_result = self.generator.tailor_resume_pdf(replacements, self.initial_resume_path)

        # Construct the expected tailored path based on initial_resume_path
        expected_base_name = os.path.basename(self.initial_resume_path) # sample_resume.pdf
        name_part, ext_part = os.path.splitext(expected_base_name) # sample_resume, .pdf
        expected_tailored_filename = f"{name_part}_tailored_{self.formatted_timestamp}{ext_part}"
        expected_tailored_full_path = os.path.join(os.path.dirname(self.initial_resume_path), expected_tailored_filename)

        self.assertEqual(tailored_path_result, expected_tailored_full_path)
        self.assertEqual(self.generator.resume_dir, expected_tailored_full_path) # resume_dir should be updated

        # Access resume_content. This will trigger the second mock from PdfReader's side_effect.
        # The AIResponseGenerator.resume_content property uses self.resume_dir to read the PDF.
        content = self.generator.resume_content

        self.assertEqual(content, "new tailored content")

        # Verify calls to PdfReader
        # First call was in tailor_resume_pdf with self.initial_resume_path
        # Second call was in resume_content property with expected_tailored_full_path
        calls = mock_pdf_reader_cls.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].args[0], self.initial_resume_path)
        self.assertEqual(calls[1].args[0], expected_tailored_full_path)

if __name__ == '__main__':
    unittest.main()
