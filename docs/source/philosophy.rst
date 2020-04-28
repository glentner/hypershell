Philosophy
==========

*Hyper-shell* was created out of a need to solve specific challenges. It's initial
implementation was only the *server* and *client* as a loose wrapper around Python's
distributed queue from the *multiprocessing* library.

Currently, there exist many nice behaviors and a generally user-friendly interface
to what remains at its core a very simple architecture. That is a feature not a
failing. There are lots of utilities out there that offer related functionality.
*Hyper-shell* is easy to understand, even for a novice programmer.

The same tool with a largely unchanged interface could be implemented in a more
efficient, and portable way using languages like *Go* or *Rust*. However, we would
loose accessibility. Further, and maybe more importantly, we would lose *Parsl*.

A future implementation of *hyper-shell* may in fact be developed in something like
*Go* or *Rust*, but today is not that day. And if it is, the interface should stay
as it is.



.. toctree::
    :maxdepth: 3
    :hidden:
