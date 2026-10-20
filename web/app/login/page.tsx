import { login } from "./actions";
const MESSAGES: Record<string, string> = {
    domain: "This e-mail domain is not allowed.",
    credentials: "Wrong e-mail or password.",
};

export default async function LoginPage({
    searchParams,
}: {
    searchParams: Promise<{ error?: string }>;
}) {
    const { error } = await searchParams;
    return (
        <main>
            <h1>Sign in</h1>
            {error && <p role="alert">{MESSAGES[error] ?? "Sign-in failed."}</p>}
            <form action={login}>
                <label>E-mail
                    <input name="email" type="email" required autoComplete="email" />
                </label>
                <label>Password
                    <input name="password" type="password" required autoComplete="current-password" />
                </label>
                <button type="submit">Sign in</button>
            </form>
        </main>
    );
}
