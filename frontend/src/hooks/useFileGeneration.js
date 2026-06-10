import { useState } from "react";
import {
  generateFileArtifact,
  previewGeneratedFile,
} from "../lib/api";

export function useFileGeneration({ setStatusMessage }) {
  const [generationPreview, setGenerationPreview] = useState(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const previewArtifact = async ({
    conversationId,
    userId,
    prompt,
    outputFormat,
    fileIds = [],
    explicitAction = "preview",
  }) => {
    setIsPreviewing(true);
    setStatusMessage("Preparing file preview...");

    try {
      const result = await previewGeneratedFile({
        conversation_id: conversationId,
        user_id: userId,
        prompt,
        output_format: outputFormat,
        file_ids: fileIds,
        explicit_action: explicitAction,
      });
      setGenerationPreview({
        kind: "preview",
        ...result,
      });
      setStatusMessage("Preview ready.");
      return result;
    } finally {
      setIsPreviewing(false);
    }
  };

  const generateArtifact = async ({
    conversationId,
    userId,
    prompt,
    outputFormat,
    fileIds = [],
    explicitAction = "generate",
  }) => {
    setIsGenerating(true);
    setStatusMessage("Generating file...");

    try {
      const result = await generateFileArtifact({
        conversation_id: conversationId,
        user_id: userId,
        prompt,
        output_format: outputFormat,
        file_ids: fileIds,
        explicit_action: explicitAction,
      });
      setGenerationPreview({
        kind: "generated",
        ...result,
      });
      setStatusMessage("File generated and attached to the conversation.");
      return result;
    } finally {
      setIsGenerating(false);
    }
  };

  return {
    generationPreview,
    isPreviewing,
    isGenerating,
    previewArtifact,
    generateArtifact,
    setGenerationPreview,
  };
}
