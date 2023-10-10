import copy

from enum import Enum
from env_v2 import EnvironmentManager, SymbolResult
from func_v2 import FunctionManager, FuncInfo
from intbase import InterpreterBase, ErrorType
from tokenizer import Tokenizer

class Object():
  def __init__(self) -> None:
    self.objects = dict()
  def set(self, method, val):
    self.objects[method] = val
  def get(self,method):
    if method in self.objects:
      return self.objects
    else:
      return None
  def value(self):
    return self.objects.items()
  def type(self):
    return Type.OBJECT
  def __str__(self):
    return f"{{method: {self.objects}}}"
  def __repr__(self):
    return self.__str__()

class Lambda():
  def __init__(self) -> None:
    self.captures = []
  def set(self, dict):
    #print("capture")
    self.captures.append(dict)
  def get_recent(self):
    #print("pass")
    return self.captures[-1]
# Enumerated type for our different language data types
class Type(Enum):
  INT = 1
  BOOL = 2
  STRING = 3
  VOID = 4
  FUNC = 5
  OBJECT = 6

# Represents a value, which has a type and its value
class Value:
  def __init__(self, type, value = None):
    self.t = type
    self.v = value

  def value(self):
    return self.v

  def set(self, other):
    self.t = other.t
    self.v = other.v

  def type(self):
    return self.t
  def __str__(self):
    return f"{{value: {self.v}, type: {self.t}}}"
  def __repr__(self):
    return self.__str__()


# Main interpreter class
class Interpreter(InterpreterBase):
  def __init__(self, console_output=True, input=None, trace_output=False):
    super().__init__(console_output, input)
    self._setup_operations()  # setup all valid binary operations and the types they work on
    self._setup_default_values()  # setup the default values for each type (e.g., bool->False)
    self.trace_output = trace_output

  # run a program, provided in an array of strings, one string per line of source code
  def run(self, program):
    self.program = program
    self._compute_indentation(program)  # determine indentation of every line
    self.tokenized_program = Tokenizer.tokenize_program(program)
    self.func_manager = FunctionManager(self.tokenized_program)
    self.ip = self.func_manager.get_function_info(InterpreterBase.MAIN_FUNC).start_ip
    self.return_stack = []
    self.lambda_captures = []
    self.lambda_return_stack = []
    self.terminate = False
    self.env_manager = EnvironmentManager()   # used to track variables/scope

    # main interpreter run loop
    while not self.terminate:
      self._process_line()

  def _process_line(self):
    if self.trace_output:
      print(f"{self.ip:04}: {self.program[self.ip].rstrip()}")
    tokens = self.tokenized_program[self.ip]
    #print(self.tokenized_program[self.ip])
    if not tokens:
      self._blank_line()
      return

    args = tokens[1:]
    match tokens[0]:
      case InterpreterBase.ASSIGN_DEF:
        self._assign(args)
      case InterpreterBase.FUNCCALL_DEF:
        self._funccall(args)
      case InterpreterBase.ENDFUNC_DEF:
        self._endfunc()
      case InterpreterBase.IF_DEF:
        self._if(args)
      case InterpreterBase.ELSE_DEF:
        self._else()
      case InterpreterBase.ENDIF_DEF:
        self._endif()
      case InterpreterBase.RETURN_DEF:
        self._return(args)
      case InterpreterBase.WHILE_DEF:
        self._while(args)
      case InterpreterBase.ENDWHILE_DEF:
        self._endwhile(args)
      case InterpreterBase.VAR_DEF: # v2 statements
        self._define_var(args)
      case InterpreterBase.LAMBDA_DEF:
        self._lambda(args) 
      case InterpreterBase.ENDLAMBDA_DEF:
        self._endlambda()
      case default:
        raise Exception(f'Unknown command: {tokens[0]}')

  def _blank_line(self):
    self._advance_to_next_statement()
  
  def _define_var(self, args):
    if len(args) < 2:
      super().error(ErrorType.SYNTAX_ERROR,"Invalid var definition syntax", self.ip)
    #print(args)
    for var_name in args[1:]:
      if self.env_manager.create_new_symbol(var_name) != SymbolResult.OK:
        super().error(ErrorType.NAME_ERROR,f"Redefinition of variable {args[1]}", self.ip)
      # is the type a valid type?
      if args[0] not in self.type_to_default:
        super().error(ErrorType.TYPE_ERROR,f"Invalid type {args[0]}", self.ip)
      #print(self.type_to_default[args[0]].value().params)
      if args[0] == InterpreterBase.OBJECT_DEF:
        self.env_manager.set(var_name, Value(Type.OBJECT,Object()))
      elif args[0] == "func":
        self.func_manager.set_function_info(var_name, copy.copy(self.type_to_default[args[0]]))
        self.env_manager.set(var_name, copy.copy(self.type_to_default[args[0]]))
      else:
        self.env_manager.set(var_name, copy.copy(self.type_to_default[args[0]]))

    self._advance_to_next_statement()
  def _assign(self, tokens):
    if len(tokens) < 2:
      super().error(ErrorType.SYNTAX_ERROR,"Invalid assignment statement")
    vname = tokens[0]
    if vname.find(".") != -1:
      object_name, method_name = vname.split(".")
      curr_object = self._get_value(object_name)
      if curr_object == None:#TODO check errors
          super().error(ErrorType.NAME_ERROR, "Issues with this type", self.ip)
      if curr_object.type() != Type.OBJECT:
        super().error(ErrorType.TYPE_ERROR, "Not an object type", self.ip)
      value_type = self._eval_expression(tokens[1:])
      #print(tokens, value_type.type())
      if value_type.type() == "func":
        self.func_manager.set_function_info(method_name, value_type)
      curr_object.value().set(method_name, value_type)
      self._set_value(object_name, curr_object)
      #if isinstance(value_type, FuncInfo):#TODO changed
      #  self.func_manager.set_function_info(vname, value_type)
    else:
      value_type = self._eval_expression(tokens[1:])
      existing_value_type = self._get_value(tokens[0])
      if existing_value_type.type() != value_type.type():
          super().error(ErrorType.TYPE_ERROR,
                        f"Trying to assign a variable of {existing_value_type.type()} to a value of {value_type.type()}",
                        self.ip)
      if(existing_value_type.type() == "func"):
        
        function_type = self.func_manager.get_function_info(tokens[1]) 
        
        self.func_manager.set_function_info(tokens[0], copy.copy(function_type))
      else:
        self._set_value(tokens[0], value_type)
    self._advance_to_next_statement()

  def _lambda(self, args):
    index = self.ip
    env = self.env_manager.get_available_vars()
    #self.lambda_captures.append(copy.deepcopy(env)) #storing it here
    obj = Lambda()
    obj.set(copy.deepcopy(env))
    self.lambda_captures.append(copy.deepcopy(obj))
    self._set_result(self.func_manager.get_function_info(self.func_manager.create_lambda_name(self.ip)))

    #print("captured ", env['x'], env['x'].type(), env['x'].value())
    while (self.tokenized_program[self.ip][0] != InterpreterBase.ENDLAMBDA_DEF) or self.indents[self.ip] != self.indents[index]:
      self.ip += 1
    self.ip += 1

    

  def _endlambda(self, return_val = None):
    #print("r")
    if not self.return_stack:  # done with main!
      self.terminate = True
    else:
      self.env_manager.pop()  # get rid of environment for the function
      if return_val:
        self._set_result(return_val)
      else:
        # return default value for type if no return value is specified. Last param of True enables
        # creation of result variable even if none exists, or is of a different type
        
        return_type = self.func_manager.get_return_type_for_enclosing_lambda_function(self.ip)
        if return_type != InterpreterBase.VOID_DEF:
          self._set_result(self.type_to_default[return_type])
      
    self.ip = self.return_stack.pop()

  def _funccall(self, args):
    if not args:
      super().error(ErrorType.SYNTAX_ERROR,"Missing function name to call", self.ip)
    if args[0] == InterpreterBase.PRINT_DEF:
      self._print(args[1:])
      self._advance_to_next_statement()
    elif args[0] == InterpreterBase.INPUT_DEF:
      self._input(args[1:])
      self._advance_to_next_statement()
    elif args[0] == InterpreterBase.STRTOINT_DEF:
      self._strtoint(args[1:])
      self._advance_to_next_statement()
    else:
      self.return_stack.append(self.ip+1)
      #print(self.ip)
      self._create_new_environment(args[0], args[1:])  # Create new environment, copy args into new env
      #print(self.env_manager.get_available_vars())
      
        


  # create a new environment for a function call
  def _create_new_environment(self, funcname, args):
    object = ""
    method = False
    if '.' in funcname:
      obj, methods = funcname.split('.')
      object = obj
      funcname = methods
      method = True
      #print(funcname)
      formal_params = self.func_manager.get_function_info(funcname)
      if formal_params is None:
        super().error(ErrorType.NAME_ERROR, f"Unknown function name {funcname}", self.ip)
      if self.env_manager.get(object).value().get(funcname)[funcname].type() != "func":
        super().error(ErrorType.TYPE_ERROR, "Incorrect func type", self.ip)
      
      if formal_params == None:
        #print("dummys")
        self.ip += 1
        return
    else:
      method = False
      formal_params = self.func_manager.get_function_info(funcname)
      
    divisor = funcname.find(".")	
    if divisor != -1:	
      if self.env_manager.get(object).value().get(funcname) is None:
        super().error(ErrorType.TYPE_ERROR, "Incorrect func type", self.ip)
    if formal_params is None:
      super().error(ErrorType.NAME_ERROR, f"Unknown function name {funcname}", self.ip)
    #print(formal_params.params, args)
    if len(formal_params.params) != len(args):
      super().error(ErrorType.NAME_ERROR,f"Mismatched parameter count in call to {funcname}", self.ip)

    tmp_mappings = {}
    if method:
      #print("here")
      tmp_mappings["this"] = self._get_value(object)
    for formal, actual in zip(formal_params.params,args):
      formal_name = formal[0]
      formal_typename = formal[1]
      arg = self._get_value(actual)
      if arg.type() != self.compatible_types[formal_typename]:
        super().error(ErrorType.TYPE_ERROR,f"Mismatched parameter type for {formal_name} in call to {funcname}", self.ip)
      #print(formal_name,arg.value())
      if isinstance(arg, FuncInfo):
        self.func_manager.set_function_info(formal_name, copy.deepcopy(arg))
      if formal_typename in self.reference_types:
        tmp_mappings[formal_name] = arg
      else:
        tmp_mappings[formal_name] = copy.copy(arg)

    # create a new environment for the target function
    # and add our parameters to the env
    self.env_manager.push()
    self.ip = self._find_first_instruction(funcname)
    if self.func_manager.get_return_type_for_enclosing_lambda_function(self.ip-1) != None:
      if len(self.lambda_captures) == 0:
        self.env_manager.import_mappings({})
      else:
        self.env_manager.import_mappings(self.lambda_captures[-1].get_recent())
        
    self.env_manager.import_mappings(tmp_mappings)
    

  def _endfunc(self, return_val = None):
    if not self.return_stack:  # done with main!
      self.terminate = True
    else:
      self.env_manager.pop()  # get rid of environment for the function
      if return_val:
        self._set_result(return_val)
      else:
        # return default value for type if no return value is specified. Last param of True enables
        # creation of result variable even if none exists, or is of a different type
        return_type = self.func_manager.get_return_type_for_enclosing_function(self.ip)
        if return_type != InterpreterBase.VOID_DEF:
          self._set_result(self.type_to_default[return_type])
      self.ip = self.return_stack.pop()

  def _if(self, args):
    
    if not args:
      super().error(ErrorType.SYNTAX_ERROR,"Invalid if syntax", self.ip)
    value_type = self._eval_expression(args)
    if value_type.type() == Type.OBJECT:
      value_type = self._get_value(str(value_type.value()))
    if value_type.type() != Type.BOOL:
      super().error(ErrorType.TYPE_ERROR,"Non-boolean if expression", self.ip)
    #print(value_type.value())
    if value_type.value():
      self._advance_to_next_statement()
      self.env_manager.block_nest()  # we're in a nested block, so create new env for it
      return
    else:
      for line_num in range(self.ip+1, len(self.tokenized_program)):
        tokens = self.tokenized_program[line_num]
        if not tokens:
          continue
        if tokens[0] == InterpreterBase.ENDIF_DEF and self.indents[self.ip] == self.indents[line_num]:
          self.ip = line_num + 1
          return
        if tokens[0] == InterpreterBase.ELSE_DEF and self.indents[self.ip] == self.indents[line_num]:
          self.ip = line_num + 1
          self.env_manager.block_nest()  # we're in a nested else block, so create new env for it
          return
    super().error(ErrorType.SYNTAX_ERROR,"Missing endif", self.ip)

  def _endif(self):
    self._advance_to_next_statement()
    self.env_manager.block_unnest()

  # we would only run this if we ran the successful if block, and fell into the else at the end of the block
  # so we need to delete the old top environment
  def _else(self):
    self.env_manager.block_unnest()   # Get rid of env for block above
    for line_num in range(self.ip+1, len(self.tokenized_program)):
      tokens = self.tokenized_program[line_num]
      if not tokens:
        continue
      if tokens[0] == InterpreterBase.ENDIF_DEF and self.indents[self.ip] == self.indents[line_num]:
          self.ip = line_num + 1
          return
    super().error(ErrorType.SYNTAX_ERROR,"Missing endif", self.ip)

  def _return(self,args):
    # do we want to support returns without values?
    lambda_type = self.func_manager.get_return_type_for_enclosing_lambda_function(self.ip)
    if lambda_type != None:
      return_type = lambda_type
    else:
      return_type = self.func_manager.get_return_type_for_enclosing_function(self.ip)
    default_value_type = self.type_to_default[return_type]
    if default_value_type.type() == Type.VOID:
      if args:
        super().error(ErrorType.TYPE_ERROR,"Returning value from void function", self.ip)
      if lambda_type != None:
        self._endlambda()
      else:
        self._endfunc()  # no return
      return
    if not args:
      if lambda_type != None:
        self._endlambda()
      else:
        self._endfunc()  # return default value
      return

    #otherwise evaluate the expression and return its value
    if default_value_type.type() != "func" or lambda_type != None:
      value_type = self._eval_expression(args)
      if value_type.type() != default_value_type.type():
        super().error(ErrorType.TYPE_ERROR,"Non-matching return type", self.ip)
    else:
      value_type = self.func_manager.get_function_info(args[0])
      if value_type == None:
        super().error(ErrorType.TYPE_ERROR,"Non-matching return type", self.ip)
      #print(value_type)
    if lambda_type != None:
      self._endlambda(value_type)
    else:
      self._endfunc(value_type)


  def _while(self, args):
    if not args:
      super().error(ErrorType.SYNTAX_ERROR,"Missing while expression", self.ip)
    value_type = self._eval_expression(args)
    if value_type.type() != Type.BOOL:
      super().error(ErrorType.TYPE_ERROR,"Non-boolean while expression", self.ip)
    if value_type.value() == False:
      self._exit_while()
      return

    # If true, we advance to the next statement
    self._advance_to_next_statement()
    # And create a new scope
    self.env_manager.block_nest()

  def _exit_while(self):
    while_indent = self.indents[self.ip]
    cur_line = self.ip + 1
    while cur_line < len(self.tokenized_program):
      if self.tokenized_program[cur_line][0] == InterpreterBase.ENDWHILE_DEF and self.indents[cur_line] == while_indent:
        self.ip = cur_line + 1
        return
      if self.tokenized_program[cur_line] and self.indents[cur_line] < self.indents[self.ip]:
        break # syntax error!
      cur_line += 1
    # didn't find endwhile
    super().error(ErrorType.SYNTAX_ERROR,"Missing endwhile", self.ip)

  def _endwhile(self, args):
    # first delete the scope
    self.env_manager.block_unnest()
    while_indent = self.indents[self.ip]
    cur_line = self.ip - 1
    while cur_line >= 0:
      if self.tokenized_program[cur_line][0] == InterpreterBase.WHILE_DEF and self.indents[cur_line] == while_indent:
        self.ip = cur_line
        return
      if self.tokenized_program[cur_line] and self.indents[cur_line] < self.indents[self.ip]:
        break # syntax error!
      cur_line -= 1
    # didn't find while
    super().error(ErrorType.SYNTAX_ERROR,"Missing while", self.ip)


  
  def _print(self, args):
    if not args:
      super().error(ErrorType.SYNTAX_ERROR,"Invalid print call syntax", self.ip)
    out = []
    for arg in args:
      val_type = self._get_value(arg)
      #print(val_type)
      out.append(str(val_type.value()))
    super().output(''.join(out))

  def _input(self, args):
    if args:
      self._print(args)
    result = super().get_input()
    self._set_result(Value(Type.STRING, result))   # return always passed back in result

  def _strtoint(self, args):
    if len(args) != 1:
      super().error(ErrorType.SYNTAX_ERROR,"Invalid strtoint call syntax", self.ip)
    value_type = self._get_value(args[0])
    if value_type.type() != Type.STRING:
      super().error(ErrorType.TYPE_ERROR,"Non-string passed to strtoint", self.ip)
    self._set_result(Value(Type.INT, int(value_type.value())))   # return always passed back in result

  def _advance_to_next_statement(self):
    # for now just increment IP, but later deal with loops, returns, end of functions, etc.
    self.ip += 1

  # Set up type-related data structures
  def _setup_default_values(self):
    # set up what value to return as the default value for each type
    self.type_to_default = {}
    self.type_to_default[InterpreterBase.INT_DEF] = Value(Type.INT,0)
    self.type_to_default[InterpreterBase.STRING_DEF] = Value(Type.STRING,'')
    self.type_to_default[InterpreterBase.BOOL_DEF] = Value(Type.BOOL,False)
    self.type_to_default[InterpreterBase.VOID_DEF] = Value(Type.VOID,None)
    self.type_to_default[InterpreterBase.FUNC_DEF] = Value("func",None)#TODO Double check
    self.type_to_default[InterpreterBase.OBJECT_DEF] = Value(Type.OBJECT, Object())

    # set up what types are compatible with what other types
    self.compatible_types = {}
    self.compatible_types[InterpreterBase.INT_DEF] = Type.INT
    self.compatible_types[InterpreterBase.STRING_DEF] = Type.STRING
    self.compatible_types[InterpreterBase.BOOL_DEF] = Type.BOOL
    self.compatible_types[InterpreterBase.REFINT_DEF] = Type.INT
    self.compatible_types[InterpreterBase.REFSTRING_DEF] = Type.STRING
    self.compatible_types[InterpreterBase.REFBOOL_DEF] = Type.BOOL
    self.compatible_types[InterpreterBase.FUNC_DEF] = "func"
    self.compatible_types[InterpreterBase.OBJECT_DEF] = Type.OBJECT
    self.reference_types = {InterpreterBase.REFINT_DEF, Interpreter.REFSTRING_DEF,
                            Interpreter.REFBOOL_DEF, InterpreterBase.OBJECT_DEF}

    # set up names of result variables: resulti, results, resultb
    self.type_to_result = {}
    self.type_to_result[Type.INT] = 'i'
    self.type_to_result[Type.STRING] = 's'
    self.type_to_result[Type.BOOL] = 'b'
    self.type_to_result["func"] = 'f'
    self.type_to_result[Type.OBJECT] = 'o'

  # run a program, provided in an array of strings, one string per line of source code
  def _setup_operations(self):
    self.binary_op_list = ['+','-','*','/','%','==','!=', '<', '<=', '>', '>=', '&', '|']
    self.binary_ops = {}
    self.binary_ops[Type.INT] = {
     '+': lambda a,b: Value(Type.INT, a.value()+b.value()),
     '-': lambda a,b: Value(Type.INT, a.value()-b.value()),
     '*': lambda a,b: Value(Type.INT, a.value()*b.value()),
     '/': lambda a,b: Value(Type.INT, a.value()//b.value()),  # // for integer ops
     '%': lambda a,b: Value(Type.INT, a.value()%b.value()),
     '==': lambda a,b: Value(Type.BOOL, a.value()==b.value()),
     '!=': lambda a,b: Value(Type.BOOL, a.value()!=b.value()),
     '>': lambda a,b: Value(Type.BOOL, a.value()>b.value()),
     '<': lambda a,b: Value(Type.BOOL, a.value()<b.value()),
     '>=': lambda a,b: Value(Type.BOOL, a.value()>=b.value()),
     '<=': lambda a,b: Value(Type.BOOL, a.value()<=b.value()),
    }
    self.binary_ops[Type.STRING] = {
     '+': lambda a,b: Value(Type.STRING, a.value()+b.value()),
     '==': lambda a,b: Value(Type.BOOL, a.value()==b.value()),
     '!=': lambda a,b: Value(Type.BOOL, a.value()!=b.value()),
     '>': lambda a,b: Value(Type.BOOL, a.value()>b.value()),
     '<': lambda a,b: Value(Type.BOOL, a.value()<b.value()),
     '>=': lambda a,b: Value(Type.BOOL, a.value()>=b.value()),
     '<=': lambda a,b: Value(Type.BOOL, a.value()<=b.value()),
    }
    self.binary_ops[Type.BOOL] = {
     '&': lambda a,b: Value(Type.BOOL, a.value() and b.value()),
     '==': lambda a,b: Value(Type.BOOL, a.value()==b.value()),
     '!=': lambda a,b: Value(Type.BOOL, a.value()!=b.value()),
     '|': lambda a,b: Value(Type.BOOL, a.value() or b.value())
    }

  def _compute_indentation(self, program):
    self.indents = [len(line) - len(line.lstrip(' ')) for line in program]

  def _find_first_instruction(self, funcname, dummy = False):
    func_info = self.func_manager.get_function_info(funcname)
    if not func_info:
      super().error(ErrorType.NAME_ERROR,f"Unable to locate {funcname} function")
    if dummy:
      return self.ip+1
    return func_info.start_ip

  # given a token name (e.g., x, 17, True, "foo"), give us a Value object associated with it

  def _get_value(self, token):
    #print(token)
    if not token:
      super().error(ErrorType.NAME_ERROR,f"Empty token", self.ip)
    if token[0] == '"':
      return Value(Type.STRING, token.strip('"'))
    if token.isdigit() or token[0] == '-':
      return Value(Type.INT, int(token))
    if token == InterpreterBase.TRUE_DEF or token == Interpreter.FALSE_DEF:
      return Value(Type.BOOL, token == InterpreterBase.TRUE_DEF)
    if token.find(".") != -1:
      object_name, method_name = token.split(".")
      curr_object = self._get_value(object_name)
      if curr_object.type() != Type.OBJECT: #TODO
        super().error(ErrorType.TYPE_ERROR, "", self.ip)
      if curr_object.value() == None or curr_object.value().get(method_name) == None:
        super().error(ErrorType.NAME_ERROR, "", self.ip)
      return curr_object.value().get(method_name)[method_name]
      
      #print( curr_object.get(method_name)[method_name])
      #return Value(Type.OBJECT, curr_object.get(method_name)[method_name].value())
    if self.func_manager.get_function_info(token) != None:
      #print("her")
      return self.func_manager.get_function_info(token)

    val = self.env_manager.get(token)
    if val != None:
      return val
    super().error(ErrorType.NAME_ERROR,f"Unknown variable {token}", self.ip)

  # given a variable name and a Value object, associate the name with the value
  def _set_value(self, varname, to_value_type):
    value_type = self.env_manager.get(varname)
    if value_type == None:
      super().error(ErrorType.NAME_ERROR,f"Assignment of unknown variable {varname}", self.ip)
    value_type.set(to_value_type)

  # bind the result[s,i,b] variable in the calling function's scope to the proper Value object
  def _set_result(self, value_type):
    # always stores result in the highest-level block scope for a function, so nested if/while blocks
    # don't each have their own version of result
    #print(value_type)
    result_var = InterpreterBase.RESULT_DEF + self.type_to_result[value_type.type()]
    
    if value_type.type() == Type.OBJECT:
      self.env_manager.create_new_symbol(result_var, True)
      new_obj = Object()
      for key,val in value_type.value().value():
        new_obj.set(key, copy.copy(val)) #TODO deepcopy
      self.env_manager.set(result_var, Value(Type.OBJECT, new_obj))
    if result_var == "resultf":
      self.env_manager.create_new_symbol(result_var, False)
      #print(value_type.start_ip)
      self.func_manager.set_function_info(result_var, value_type)#TODO Maybe copy.copy
      pass
    else:
      self.env_manager.create_new_symbol(result_var, True)  # create in top block if it doesn't exist
      self.env_manager.set(result_var, copy.copy(value_type))

  # evaluate expressions in prefix notation: + 5 * 6 x
  def _eval_expression(self, tokens):
    stack = []

    for token in reversed(tokens):
      if token in self.binary_op_list:
        v1 = stack.pop()
        v2 = stack.pop()
        if v1.type() != v2.type():
          super().error(ErrorType.TYPE_ERROR,f"Mismatching types {v1.type()} and {v2.type()}", self.ip)
        operations = self.binary_ops[v1.type()]
        if token not in operations:
          super().error(ErrorType.TYPE_ERROR,f"Operator {token} is not compatible with {v1.type()}", self.ip)
        #print("gr",v1.value(),v2.value())
        stack.append(operations[token](v1,v2))
      elif token == '!':
        v1 = stack.pop()
        if v1.type() != Type.BOOL:
          super().error(ErrorType.TYPE_ERROR,f"Expecting boolean for ! {v1.type()}", self.ip)
        stack.append(Value(Type.BOOL, not v1.value()))
      elif token.find('.') != -1:
        object_name, method_name = token.split(".")
        curr_object = self._get_value(object_name)
        #print(curr_object.value())
        #TODO add error checking
        #print("eval", curr_object.value().get(method_name)[method_name])
        value_type = curr_object.value().get(method_name)[method_name]
        stack.append(value_type)
      else:
        value_type = self._get_value(token)
        stack.append(value_type)

    if len(stack) != 1:
      super().error(ErrorType.SYNTAX_ERROR,f"Invalid expression", self.ip)

    return stack[0]
