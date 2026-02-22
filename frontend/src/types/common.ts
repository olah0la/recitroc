export type ID = number;
export type Timestamp = string; // ISO 8601 format

export interface Auditable {
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
