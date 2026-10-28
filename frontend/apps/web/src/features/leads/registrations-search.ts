import { z } from "zod";

export const registrationSearch = z.object({
  q: z.string().optional(),
  channel: z.string().optional(),
  qr_status: z.string().optional(),
  email_status: z.string().optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(20),
});
