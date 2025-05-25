import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";


// Create a matcher for public routes
const publicRoutes = createRouteMatcher(['/sign-in(.*)']);

// Update the middleware to allow access to sign-in page even when authenticated
export default clerkMiddleware(async (auth, req) => {
  if (!publicRoutes(req)) await auth.protect();
});

export const config = {
  matcher: ['/((?!.+\\.[\\w]+$|_next).*)', '/', '/(api|trpc)(.*)'],
};