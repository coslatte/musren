import type { Operation } from "../api/jobs";

export const OPERATIONS: {
  id: Operation;
  label: string;
  title: string;
  action: string;
}[] = [
  { id: "rename", label: "Rename", title: "Rename files", action: "Rename" },
  {
    id: "lyrics",
    label: "Lyrics",
    title: "Add synchronized lyrics",
    action: "Add lyrics",
  },
  { id: "covers", label: "Covers", title: "Add album covers", action: "Add covers" },
  {
    id: "recognize",
    label: "Recognize",
    title: "Recognize audio",
    action: "Recognize",
  },
  { id: "albums", label: "Albums", title: "Organize into albums", action: "Organize" },
  {
    id: "revert",
    label: "Revert",
    title: "Move files to this folder",
    action: "Move files",
  },
];
