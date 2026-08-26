export interface DocumentItem {
  filename: string;
  file_type: string;
  chunk_count: number;
}

export interface DocumentChunk {
  chunk_id: string;
  parent_chunk_id: string;
  root_chunk_id: string;
  chunk_level: 1 | 2 | 3 | number;
  chunk_idx: number;
  page_number: number;
  text: string;
}

export interface DocumentChunkTreeNode extends DocumentChunk {
  children: DocumentChunkTreeNode[];
}

export interface UploadStep {
  key: string;
  label: string;
  percent: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  message: string;
}

export interface UploadJob {
  job_id: string;
  status: 'running' | 'completed' | 'failed';
  message: string;
  steps: UploadStep[];
}

export interface DeleteStep {
  key: string;
  label: string;
  percent: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  message: string;
}

export interface DeleteJob {
  job_id: string;
  status: 'running' | 'completed' | 'failed';
  message: string;
  steps: DeleteStep[];
}

export interface ActiveDeleteJob {
  jobId?: string;
  status: 'running' | 'completed' | 'failed';
  message: string;
  collapsed: boolean;
  steps: DeleteStep[];
}
