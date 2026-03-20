File "/mount/src/shield716/app.py", line 54, in <module>
    df = get_data()
         ^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/streamlit/runtime/caching/cache_utils.py", line 281, in __call__
    return self._get_or_create_cached_value(args, kwargs, spinner_message)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/streamlit/runtime/caching/cache_utils.py", line 326, in _get_or_create_cached_value
    return self._handle_cache_miss(cache, value_key, func_args, func_kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/streamlit/runtime/caching/cache_utils.py", line 385, in _handle_cache_miss
    computed_value = self._info.func(*func_args, **func_kwargs)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/mount/src/shield716/app.py", line 43, in get_data
    df = pd.DataFrame({
         ^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/frame.py", line 782, in __init__
    mgr = dict_to_mgr(data, index, columns, dtype=dtype, copy=copy, typ=manager)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/internals/construction.py", line 503, in dict_to_mgr
    return arrays_to_mgr(arrays, columns, index, dtype=dtype, typ=typ, consolidate=copy)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/internals/construction.py", line 119, in arrays_to_mgr
    arrays, refs = _homogenize(arrays, index, dtype)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/internals/construction.py", line 629, in _homogenize
    val = sanitize_array(val, index, dtype=dtype, copy=False)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/construction.py", line 630, in sanitize_array
    return sanitize_array(
           ^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/construction.py", line 656, in sanitize_array
    subarr = _sanitize_ndim(subarr, data, dtype, index, allow_2d=allow_2d)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.12/site-packages/pandas/core/construction.py", line 715, in _sanitize_ndim
    raise ValueError(
