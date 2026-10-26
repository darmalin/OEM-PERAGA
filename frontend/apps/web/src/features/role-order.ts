/** Role list position: smaller numbers come first (highest access). */
export const ORDER_HELP = "Lists show roles from the smallest number: 1 is the highest access.";

export const ORDER_RULES = {
  required: "Enter a number.",
  min: { value: 1, message: "Use 1 or more." },
  max: { value: 9999, message: "Use 9999 or less." },
  pattern: { value: /^\d+$/, message: "Use a whole number." },
};
