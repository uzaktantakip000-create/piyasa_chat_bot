"""
Tests for LLM Batch Generation

Tests batch generation functionality with mock LLM responses.
"""

import pytest
from unittest.mock import Mock, patch
from llm_client_batch import LLMBatchClient, generate_batch


class TestLLMBatchClient:
    """Test suite for LLMBatchClient"""

    @patch('llm_client_batch.LLMClient')
    def test_batch_client_initialization(self, mock_llm_class):
        """Test batch client initializes correctly"""
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm

        client = LLMBatchClient()
        assert client.max_workers > 0
        assert client.llm_client is not None

    @patch('llm_client_batch.LLMClient')
    def test_generate_batch_empty_prompts(self, mock_llm_class):
        """Test batch generation with empty prompts list"""
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm

        client = LLMBatchClient()
        results = client.generate_batch(prompts=[])
        assert results == []

    @patch('llm_client_batch.LLMClient')
    def test_generate_batch_success(self, mock_llm_class):
        """Test successful batch generation"""
        # Mock LLM responses
        mock_llm = Mock()
        mock_llm.generate.side_effect = [
            "Response 1",
            "Response 2",
            "Response 3",
        ]
        mock_llm_class.return_value = mock_llm

        client = LLMBatchClient()
        client.llm_client = mock_llm

        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        results = client.generate_batch(prompts=prompts)

        assert len(results) == 3
        assert all(result is not None for result in results)
        assert mock_llm.generate.call_count == 3

    @patch('llm_client_batch.LLMClient')
    def test_generate_batch_partial_failure(self, mock_llm_class):
        """Test batch generation with some failures"""
        # Mock LLM responses (some None)
        mock_llm = Mock()
        mock_llm.generate.side_effect = [
            "Response 1",
            None,  # Failed generation
            "Response 3",
        ]
        mock_llm_class.return_value = mock_llm

        client = LLMBatchClient()
        client.llm_client = mock_llm

        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        results = client.generate_batch(prompts=prompts)

        assert len(results) == 3
        assert results[0] == "Response 1"
        assert results[1] is None
        assert results[2] == "Response 3"

    @patch('llm_client_batch.LLMClient')
    def test_generate_with_fallback(self, mock_llm_class):
        """Test batch generation with automatic retry"""
        # Mock LLM responses (first attempt has failure, retry succeeds)
        mock_llm = Mock()
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # Second call (index 1) fails first time
                return None
            return f"Response {call_count[0]}"

        mock_llm.generate.side_effect = side_effect
        mock_llm_class.return_value = mock_llm

        client = LLMBatchClient()
        client.llm_client = mock_llm

        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        results = client.generate_with_fallback(prompts=prompts, retry_failed=True)

        assert len(results) == 3
        # After retry, all should succeed
        assert all(result is not None for result in results)

    @patch('llm_client_batch.LLMClient')
    def test_generate_batch_preserve_order(self, mock_llm_class):
        """Test that batch generation preserves order"""
        # Mock LLM responses
        mock_llm = Mock()
        mock_llm.generate.side_effect = lambda user_prompt, **kwargs: f"Response for: {user_prompt}"
        mock_llm_class.return_value = mock_llm

        client = LLMBatchClient()
        client.llm_client = mock_llm

        prompts = ["First", "Second", "Third", "Fourth", "Fifth"]
        results = client.generate_batch(prompts=prompts, preserve_order=True)

        assert len(results) == 5
        assert results[0] == "Response for: First"
        assert results[1] == "Response for: Second"
        assert results[2] == "Response for: Third"
        assert results[3] == "Response for: Fourth"
        assert results[4] == "Response for: Fifth"

    @patch('llm_client_batch.LLMClient')
    def test_convenience_function(self, mock_llm_class):
        """Test convenience function generate_batch()"""
        mock_llm = Mock()
        mock_llm.generate.return_value = "Response"
        mock_llm_class.return_value = mock_llm

        prompts = ["Prompt 1", "Prompt 2"]
        results = generate_batch(prompts=prompts)

        assert len(results) == 2
        assert all(result == "Response" for result in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
