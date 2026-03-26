import { useState } from "react";
import { uploadConversationFiles } from "../lib/api";

export function useConversationUploads({
  mergeConversationFiles,
  setStatusMessage,
}) {
  const [isUploadingFiles, setIsUploadingFiles] = useState(false);

  const uploadFiles = async ({ conversationId, files }) => {
    if (files.length === 0) {
      return [];
    }

    setIsUploadingFiles(true);
    setStatusMessage("Uploading files...");

    try {
      const uploadedFiles = await uploadConversationFiles({
        conversationId,
        files,
      });
      mergeConversationFiles(conversationId, uploadedFiles);
      return uploadedFiles;
    } finally {
      setIsUploadingFiles(false);
    }
  };

  return {
    isUploadingFiles,
    uploadFiles,
  };
}
