# spiderweb

As a professional web developer focusing on arcane uses of Django for arcane purposes, it occurred to me a little while ago that I didn't actually know how a web framework _worked_.

> So I built one.

This is `spiderweb`, a web framework that's just big enough to hold a spider. When building it, my goals were simple:

- Learn a lot
- Create an unholy blend of Django and Flask
- Not look at any existing code. Go off of vibes alone and try to solve all the problems I could think of in my own way

> [!WARNING]
> This is a learning project. It should not be used for production without heavy auditing. It's not secure. It's not fast. It's not well-tested. It's not well-documented. It's not well-anything. It's a learning project.
> 
> That being said, it's fun and it works, so I'm counting that as a win.


Here's a non-exhaustive list of things this can do:

  * Function-based views
  * Optional Flask-style URL routing
  * Optional Django-style URL routing
  * URLs with variables in them a lá Django
  * Full middleware implementation
  * Limit routes by HTTP verbs
    * (Only GET and POST are implemented right now)
  * Custom error routes
  * Built-in dev server
  * Gunicorn support
  * HTML templates with Jinja2
  * Static files support
  * Cookies (reading and setting)
  * Optional append_slash (with automatic redirects!)
  * ~~CSRF middleware implementation~~ (it's there, but it's crappy and unsafe. This might be beyond my skillset.)
  * Optional POST data validation middleware with Pydantic
  * Database support (using Peewee, but the end user can use whatever they want as long as there's a Peewee driver for it)
  * Session middleware with built-in session store
  * Tests (currently a little over 80% coverage)

The TODO list:

  * Fix CSRF middleware
  * Add more HTTP verbs
