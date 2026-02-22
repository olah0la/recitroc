import type { ID, Auditable } from './common';

export interface Category {
  id: ID;
  name: string;
  parentCategory?: Category;
}

export interface Item extends Auditable {
  id: ID;
  title: string;
  description: string;
  category: Category;
  imageUrl?: string;
  ownerId: ID;
  tags: string[];
}

export default Item;
