import { render, screen } from "@testing-library/react";
import App from "./App";

describe("seller portal", () => {
  beforeEach(() => sessionStorage.clear());

  it("explains the acquisition flow before an application starts", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /we buy your music catalog/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /preview only/i })).toBeDisabled();
    expect(screen.getByText(/structured offer with no obligation to accept/i)).toBeInTheDocument();
  });
});
